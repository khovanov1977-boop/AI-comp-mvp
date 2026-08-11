import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.character import Character, CharacterProfile, CharacterScene, CharacterState
from app.models.memory import Memory
from app.models.message import Message
from app.models.user import User
from app.config import Settings
from app.providers.llm_factory import get_llm_provider
from app.providers.llm_mock import generate_reply
from app.providers.llm_openai_compatible import LLMProviderError
from app.services.character_engine import analyze_user_message, update_state_after_message
from app.services.language_robustness import analyze_language_robustness
from app.services.orchestrator import handle_chat_message
from app.services.memory_service import remember_user_message
from app.services.orchestrator_context import build_orchestrator_context
from app.services.prompt_builder import build_provider_prompt
from app.services.response_sanitizer import sanitize_assistant_reply
from app.services.scene_service import get_or_create_scene
from app.services.time_context import describe_daylight_context, describe_time_of_day, infer_timezone


class OrchestratorContextTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()
        self.character = self.create_character()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def create_character(self) -> Character:
        user = User(
            email="test@example.com",
            display_name="Tester",
            city="Moscow",
            country="Russia",
            timezone="Europe/Moscow",
            language="ru",
        )
        character = Character(
            user=user,
            name="Alice",
            gender="female",
            relationship_mode="friend",
        )
        character.profile = CharacterProfile(
            personality_description="Warm and thoughtful",
            communication_style="Gentle, concise",
            biography="Lives in the test fixture",
            boundaries="No medical advice",
            likes="Tea",
            dislikes="Noise",
            language="ru",
            user_nickname="Tester",
        )
        character.state = CharacterState(
            mood="curious",
            trust_level=21,
            attachment_level=13,
            energy_level=74,
        )
        self.db.add(character)
        self.db.commit()
        self.db.refresh(character)
        return character

    def add_context_records(self) -> None:
        now = datetime.now(timezone.utc)
        self.db.add_all(
            [
                Memory(character_id=self.character.id, memory_type="user_fact", content="favorite city Ukhta", importance=2),
                Memory(character_id=self.character.id, memory_type="preference", content="likes tea", importance=3),
                Memory(character_id=self.character.id, memory_type="life_event", content="birthday 18.12.1977", importance=2),
                Memory(
                    character_id=self.character.id,
                    memory_type="relationship_note",
                    content="prefers trust",
                    importance=1,
                ),
                Memory(character_id=self.character.id, memory_type="system_note", content="test note", importance=1),
                Message(character_id=self.character.id, role="user", content="hello", message_type="text", created_at=now),
                Message(
                    character_id=self.character.id,
                    role="assistant",
                    content="hi",
                    message_type="text",
                    created_at=now + timedelta(seconds=1),
                ),
            ]
        )
        self.db.commit()

    def test_context_builder_includes_profile_state_memory_messages_and_current_message(self) -> None:
        self.add_context_records()

        context = build_orchestrator_context(self.db, self.character, "current test message")

        self.assertEqual(context.character_id, self.character.id)
        self.assertEqual(context.character_name, "Alice")
        self.assertEqual(context.character_gender, "female")
        self.assertEqual(context.relationship_mode, "friend")
        self.assertEqual(context.profile.personality_description, "Warm and thoughtful")
        self.assertEqual(context.profile.communication_style, "Gentle, concise")
        self.assertEqual(context.profile.biography, "Lives in the test fixture")
        self.assertEqual(context.profile.boundaries, "No medical advice")
        self.assertEqual(context.profile.likes, "Tea")
        self.assertEqual(context.profile.dislikes, "Noise")
        self.assertEqual(context.profile.language, "ru")
        self.assertEqual(context.profile.user_nickname, "Tester")
        self.assertEqual(context.state.mood, "curious")
        self.assertEqual(context.state.trust, 21)
        self.assertEqual(context.state.attachment, 13)
        self.assertEqual(context.state.energy, 74)
        self.assertEqual(context.user_context.display_name, "Tester")
        self.assertEqual(context.user_context.city, "Moscow")
        self.assertEqual(context.user_context.country, "Russia")
        self.assertEqual(context.user_context.timezone, "Europe/Moscow")
        self.assertEqual(context.user_context.language, "ru")
        self.assertTrue(context.user_context.local_date)
        self.assertTrue(context.user_context.local_time)
        self.assertTrue(context.user_context.local_datetime_iso)
        self.assertTrue(context.user_context.weekday)
        self.assertTrue(context.user_context.time_of_day)
        self.assertTrue(context.user_context.daylight_context)
        self.assertEqual(context.scene_context.presence_mode, "remote_chat")
        self.assertEqual(context.scene_context.location_name, "Private chat")
        self.assertFalse(context.scene_context.can_use_physical_touch)
        self.assertFalse(context.scene_context.can_share_immediate_physical_space)
        self.assertIn("Remote chat", context.world_state.reality_summary)
        self.assertEqual(context.world_state.location_type, "remote_chat")
        self.assertEqual(context.world_state.posture_summary, "separate_places")
        self.assertIn("impossible", context.world_state.physical_touch_policy)
        self.assertFalse(context.language_context.has_colloquial_language)
        self.assertEqual(context.language_context.slang_terms, {})
        self.assertEqual(context.language_context.smileys, {})
        self.assertEqual(context.language_context.typo_hints, {})
        self.assertEqual(set(context.memory.keys()), {"user_fact", "preference", "life_event", "relationship_note", "system_note"})
        self.assertEqual(context.memory["preference"][0].content, "likes tea")
        self.assertEqual([message.content for message in context.recent_messages], ["hello", "hi"])
        self.assertEqual(context.current_user_message, "current test message")

    def test_memory_extraction_stores_basic_categories(self) -> None:
        preference = remember_user_message(
            self.db,
            self.character.id,
            "\u044f \u043b\u044e\u0431\u043b\u044e \u0447\u0430\u0439 \u043f\u043e \u0443\u0442\u0440\u0430\u043c",
        )
        life_event = remember_user_message(
            self.db,
            self.character.id,
            "\u044f \u0440\u043e\u0434\u0438\u043b\u0441\u044f 18 \u0434\u0435\u043a\u0430\u0431\u0440\u044f 1977 \u0433\u043e\u0434\u0430",
        )
        user_fact = remember_user_message(
            self.db,
            self.character.id,
            "\u043c\u043e\u0439 \u0431\u0440\u0430\u0442 \u0421\u0435\u0440\u0433\u0435\u0439 \u0436\u0438\u0432\u0435\u0442 \u0440\u044f\u0434\u043e\u043c",
        )
        ignored = remember_user_message(self.db, self.character.id, "\u043a\u043e\u0440\u043e\u0442\u043a\u043e")

        self.assertEqual(preference.memory_type, "preference")
        self.assertEqual(
            preference.content,
            "\u044f \u043b\u044e\u0431\u043b\u044e \u0447\u0430\u0439 \u043f\u043e \u0443\u0442\u0440\u0430\u043c",
        )
        self.assertEqual(life_event.memory_type, "life_event")
        self.assertEqual(
            life_event.content,
            "\u0434\u0430\u0442\u0430 \u0440\u043e\u0436\u0434\u0435\u043d\u0438\u044f 18.12.1977",
        )
        self.assertEqual(user_fact.memory_type, "user_fact")
        self.assertIsNone(ignored)

    def test_state_update_logic_is_stable_and_capped(self) -> None:
        self.character.state.trust_level = 100
        self.character.state.attachment_level = 99
        self.character.state.energy_level = 0

        state = update_state_after_message(self.character, "I love this, thank you :)")

        self.assertEqual(state.mood, "warm")
        self.assertEqual(state.trust_level, 100)
        self.assertEqual(state.attachment_level, 100)
        self.assertEqual(state.energy_level, 0)

    def test_state_engine_detects_conflict_and_smileys(self) -> None:
        conflict = analyze_user_message("Ты перепутал мое имя, не называй меня так")
        smile = analyze_user_message("Спасибо, мне хорошо :)")

        self.assertEqual(conflict.mood, "guarded")
        self.assertLess(conflict.trust_delta, 0)
        self.assertEqual(smile.mood, "warm")
        self.assertGreater(smile.trust_delta, 0)

    def test_language_robustness_detects_slang_smileys_and_typos(self) -> None:
        signal = analyze_language_robustness("Сорян, щас норм вайб :)")

        self.assertTrue(signal.has_colloquial_language)
        self.assertEqual(signal.slang_terms["сорян"], "sorry, informal")
        self.assertEqual(signal.slang_terms["вайб"], "mood or atmosphere")
        self.assertEqual(signal.smileys[":)"], "friendly warmth or a light smile")
        self.assertEqual(signal.typo_hints["щас"], "сейчас")
        self.assertIn("Do not correct", signal.guidance)

    def test_debug_endpoint_returns_structured_context(self) -> None:
        self.add_context_records()

        def override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        try:
            client = TestClient(app)
            response = client.post(
                "/debug/orchestrator-context",
                json={"character_id": self.character.id, "message": "endpoint message"},
            )
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["character_id"], self.character.id)
        self.assertEqual(payload["character_name"], "Alice")
        self.assertEqual(payload["relationship_mode"], "friend")
        self.assertEqual(payload["profile"]["personality_description"], "Warm and thoughtful")
        self.assertEqual(payload["state"]["mood"], "curious")
        self.assertEqual(payload["user_context"]["city"], "Moscow")
        self.assertEqual(payload["user_context"]["timezone"], "Europe/Moscow")
        self.assertEqual(payload["scene_context"]["presence_mode"], "remote_chat")
        self.assertEqual(payload["scene_context"]["location_name"], "Private chat")
        self.assertEqual(payload["world_state"]["location_type"], "remote_chat")
        self.assertIn("language_context", payload)
        self.assertFalse(payload["language_context"]["has_colloquial_language"])
        self.assertEqual(set(payload["memory"].keys()), {"user_fact", "preference", "life_event", "relationship_note", "system_note"})
        self.assertEqual(payload["recent_messages"][0]["content"], "hello")
        self.assertEqual(payload["current_user_message"], "endpoint message")

    def test_character_creation_creates_default_scene(self) -> None:
        def override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        try:
            client = TestClient(app)
            response = client.post(
                "/characters",
                json={
                    "name": "Sergey",
                    "gender": "male",
                    "relationship_mode": "friend",
                    "language": "ru",
                },
            )
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        character_id = response.json()["id"]
        scene = self.db.scalar(select(CharacterScene).where(CharacterScene.character_id == character_id))
        self.assertIsNotNone(scene)
        self.assertEqual(scene.presence_mode, "remote_chat")

    def test_mock_provider_can_be_called_through_provider_interface(self) -> None:
        self.add_context_records()
        context = build_orchestrator_context(self.db, self.character, "How are you?")

        provider_reply = get_llm_provider("mock").generate_reply(context)
        legacy_reply = generate_reply(self.character, context.current_user_message, context.recent_messages)

        self.assertEqual(provider_reply, legacy_reply)

    def test_prompt_builder_includes_key_context_fields(self) -> None:
        self.add_context_records()
        context = build_orchestrator_context(self.db, self.character, "current test message")

        prompt = build_provider_prompt(context)

        self.assertIn("character_name: Alice", prompt.system)
        self.assertIn("character_gender: female", prompt.system)
        self.assertIn("user_name: Tester", prompt.system)
        self.assertIn("relationship_mode: friend", prompt.system)
        self.assertIn("user_city: Moscow", prompt.system)
        self.assertIn("user_country: Russia", prompt.system)
        self.assertIn("user_timezone: Europe/Moscow", prompt.system)
        self.assertIn("exact_current_user_local_date:", prompt.system)
        self.assertIn("current_user_weekday:", prompt.system)
        self.assertIn("current_user_time_of_day:", prompt.system)
        self.assertIn("current_user_daylight_context:", prompt.system)
        self.assertIn("presence_mode: remote_chat", prompt.system)
        self.assertIn("location_name: Private chat", prompt.system)
        self.assertIn("Current reality / world state", prompt.system)
        self.assertIn("reality_summary: Remote chat", prompt.system)
        self.assertIn("physical_touch_policy:", prompt.system)
        self.assertIn("Before replying, silently check", prompt.system)
        self.assertIn("Language robustness context:", prompt.system)
        self.assertIn("detected_slang_terms:", prompt.system)
        self.assertIn("detected_smileys:", prompt.system)
        self.assertIn("detected_typo_hints:", prompt.system)
        self.assertIn("personality_description: Warm and thoughtful", prompt.system)
        self.assertIn("communication_style: Gentle, concise", prompt.system)
        self.assertIn("boundaries: No medical advice", prompt.system)
        self.assertIn("mood: curious", prompt.system)
        self.assertIn("mood_human_ru:", prompt.system)
        self.assertIn("живой интерес", prompt.system)
        self.assertIn("trust: 21", prompt.system)
        self.assertIn("State behavior guidance:", prompt.system)
        self.assertIn("Let mood influence tone naturally", prompt.system)
        self.assertIn("use mood_human_ru as the emotional nuance", prompt.system)
        self.assertIn("Do not announce state numbers", prompt.system)
        self.assertIn("preference:", prompt.system)
        self.assertIn("- likes tea", prompt.system)
        self.assertIn("Never confuse character_name and user_name", prompt.system)
        self.assertIn("do not invent a name", prompt.system)
        self.assertIn("obey the correction", prompt.system)
        self.assertIn("Never describe the character in third person", prompt.system)
        self.assertIn("Do not mechanically repeat", prompt.system)
        self.assertIn("Do not claim to browse the internet", prompt.system)
        self.assertIn("assume the character shares the user's city and timezone", prompt.system)
        self.assertIn("Do not add or subtract the timezone offset again", prompt.system)
        self.assertIn("answer with exact_current_user_local_time directly", prompt.system)
        self.assertIn("Do not estimate, round, or shift it by a few minutes", prompt.system)
        self.assertIn("Use current_user_time_of_day and current_user_daylight_context", prompt.system)
        self.assertIn("Do not suggest sunset", prompt.system)
        self.assertIn("do not suggest immediate in-person activities together", prompt.system)
        self.assertIn("Treat world_state as the current reality", prompt.system)
        self.assertIn("Do not invent a different place", prompt.system)
        self.assertIn("If the user asks where you are", prompt.system)
        self.assertIn("Never output tool calls", prompt.system)
        self.assertIn("<tool_call>", prompt.system)
        self.assertIn("Understand slang, smileys, typos", prompt.system)
        self.assertIn("Do not lecture the user about slang or spelling", prompt.system)
        self.assertEqual([message.content for message in prompt.messages], ["hello", "hi", "current test message"])

    def test_response_sanitizer_removes_tool_call_artifacts(self) -> None:
        reply = "Я уже рядом, слышишь? wait <tool_call>\nenter</tool_call>\nИ говорю с тобой."

        cleaned = sanitize_assistant_reply(reply)

        self.assertEqual(cleaned, "Я уже рядом, слышишь?\nИ говорю с тобой.")
        self.assertNotIn("tool_call", cleaned)

    def test_same_place_scene_allows_physical_presence_in_context(self) -> None:
        self.character.scene = CharacterScene(
            presence_mode="same_place",
            location_name="Park bench",
            location_description="The user and character are sitting together on a bench in the park.",
            user_position="sitting on the bench",
            character_position="sitting on the same bench",
        )
        self.db.add(self.character)
        self.db.commit()

        context = build_orchestrator_context(self.db, self.character, "we are here")

        self.assertEqual(context.scene_context.presence_mode, "same_place")
        self.assertEqual(context.scene_context.location_name, "Park bench")
        self.assertTrue(context.scene_context.can_use_physical_touch)
        self.assertTrue(context.scene_context.can_share_immediate_physical_space)
        self.assertIn("Same physical scene", context.world_state.reality_summary)
        self.assertEqual(context.world_state.location_type, "outdoor_place")
        self.assertEqual(context.world_state.posture_summary, "seated")
        self.assertIn("possible", context.world_state.physical_touch_policy)

    def test_get_or_create_scene_reuses_existing_scene(self) -> None:
        first_scene = get_or_create_scene(self.db, self.character)
        second_scene = get_or_create_scene(self.db, self.character)

        self.assertEqual(first_scene.id, second_scene.id)
        self.assertEqual(first_scene.character_id, self.character.id)

    def test_timezone_can_be_inferred_from_city(self) -> None:
        self.assertEqual(infer_timezone("Ухта", "Россия"), "Europe/Moscow")
        self.assertEqual(infer_timezone("Novosibirsk", "Russia"), "Asia/Novosibirsk")

    def test_time_of_day_context_guides_realistic_suggestions(self) -> None:
        self.assertEqual(describe_time_of_day(23), "late_evening")
        self.assertIn("too late for ordinary sunset", describe_daylight_context(23))

    def test_memory_extraction_does_not_store_user_corrections_as_facts(self) -> None:
        corrections = [
            "\u043f\u043e\u0447\u0435\u043c\u0443 \u0442\u044b \u043d\u0430\u0437\u044b\u0432\u0430\u0435\u0448\u044c \u043c\u0435\u043d\u044f \u041d\u0430\u0442\u0430\u043b\u0438?",
            "\u044f \u043d\u0435 \u0433\u043e\u0432\u043e\u0440\u0438\u043b\u0430 \u0442\u0430\u043a\u043e\u0433\u043e",
            "do not call me Alex",
        ]

        for correction in corrections:
            self.assertIsNone(remember_user_message(self.db, self.character.id, correction))

        memories = self.db.query(Memory).filter(Memory.character_id == self.character.id).all()
        self.assertEqual(memories, [])

    def test_config_defaults_to_mock_provider(self) -> None:
        self.assertEqual(Settings.model_fields["llm_provider"].default, "mock")
        self.assertEqual(get_llm_provider("mock").name, "mock")

    def test_chat_flow_returns_mock_reply_through_provider_interface(self) -> None:
        with patch("app.services.orchestrator.get_llm_provider", return_value=get_llm_provider("mock")):
            reply, assistant_message = handle_chat_message(self.db, self.character, "I am testing chat flow")

        self.assertEqual(reply, assistant_message.content)
        self.assertTrue(reply)
        messages = self.db.query(Message).filter(Message.character_id == self.character.id).order_by(Message.created_at.asc()).all()
        self.assertEqual([message.role for message in messages], ["user", "assistant"])
        self.assertIn(self.character.state.mood, {"attentive", "curious", "warm", "concerned", "guarded"})

    def test_chat_flow_preserves_user_message_when_provider_fails(self) -> None:
        class FailingProvider:
            def generate_reply(self, _context):
                raise LLMProviderError("LLM provider returned HTTP 429")

        with patch("app.services.orchestrator.get_llm_provider", return_value=FailingProvider()):
            with self.assertRaisesRegex(LLMProviderError, "HTTP 429"):
                handle_chat_message(self.db, self.character, "Please do not lose this")

        messages = self.db.query(Message).filter(Message.character_id == self.character.id).order_by(Message.created_at.asc()).all()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].role, "user")
        self.assertEqual(messages[0].content, "Please do not lose this")

    def test_chat_endpoint_returns_service_unavailable_for_provider_errors(self) -> None:
        class FailingProvider:
            def generate_reply(self, _context):
                raise LLMProviderError("LLM provider returned HTTP 429")

        def override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch("app.services.orchestrator.get_llm_provider", return_value=FailingProvider()):
                client = TestClient(app)
                response = client.post(
                    "/chat",
                    json={"character_id": self.character.id, "message": "Keep this message"},
                )
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["detail"]["error"], "llm_provider_error")
        self.assertEqual(payload["detail"]["message"], "LLM provider returned HTTP 429")
        messages = self.db.query(Message).filter(Message.character_id == self.character.id).order_by(Message.created_at.asc()).all()
        self.assertEqual([message.content for message in messages], ["Keep this message"])

    def test_chat_endpoint_returns_service_unavailable_for_unexpected_errors(self) -> None:
        class FailingProvider:
            def generate_reply(self, _context):
                raise RuntimeError("Unexpected provider failure")

        def override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch("app.services.orchestrator.get_llm_provider", return_value=FailingProvider()):
                client = TestClient(app)
                response = client.post(
                    "/chat",
                    json={"character_id": self.character.id, "message": "Keep this too"},
                )
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["detail"]["error"], "chat_error")
        self.assertEqual(payload["detail"]["message"], "Unexpected provider failure")

    def test_chat_retry_reuses_last_failed_user_message_without_duplicate(self) -> None:
        class FailingProvider:
            def generate_reply(self, _context):
                raise LLMProviderError("LLM provider returned HTTP 429")

        def override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        try:
            client = TestClient(app)
            with patch("app.services.orchestrator.get_llm_provider", return_value=FailingProvider()):
                failed_response = client.post(
                    "/chat",
                    json={"character_id": self.character.id, "message": "Please retry this"},
                )
            with patch("app.services.orchestrator.get_llm_provider", return_value=get_llm_provider("mock")):
                retry_response = client.post(
                    "/chat/retry",
                    json={"character_id": self.character.id},
                )
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(failed_response.status_code, 503)
        self.assertEqual(retry_response.status_code, 200)
        messages = self.db.query(Message).filter(Message.character_id == self.character.id).order_by(Message.created_at.asc()).all()
        self.assertEqual([message.role for message in messages], ["user", "assistant"])
        self.assertEqual(messages[0].content, "Please retry this")


if __name__ == "__main__":
    unittest.main()
