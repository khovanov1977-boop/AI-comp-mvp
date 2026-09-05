import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.character import Character, CharacterProfile, CharacterScene, CharacterState
from app.models.media_asset import IdentityReference, MediaAsset
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
from app.services.name_addressing import build_user_address_policy, contains_name, decide_name_usage
from app.services.orchestrator_context import build_orchestrator_context
from app.services.prompt_builder import build_provider_prompt
from app.services.response_sanitizer import sanitize_assistant_reply
from app.services.roleplay_protocol import analyze_roleplay_notation
from app.services.scene_service import get_or_create_scene, update_scene
from app.schemas.scene import SceneUpdate
from app.schema_sync import (
    ensure_dev_schema,
    legacy_local_timestamp_to_utc,
    normalize_legacy_finished_scene_memory,
)
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
            formal_name="Алексей",
            preferred_name="Лёша",
            casual_name="Лёха",
            vocative_name="Лёш",
            age=48,
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
            warmth=82,
            initiative=68,
            playfulness=37,
            directness=61,
            emotionality=74,
            rationality=56,
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
        now = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=5)
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
        self.assertEqual(context.profile.warmth, 82)
        self.assertEqual(context.profile.initiative, 68)
        self.assertEqual(context.profile.playfulness, 37)
        self.assertEqual(context.profile.directness, 61)
        self.assertEqual(context.profile.emotionality, 74)
        self.assertEqual(context.profile.rationality, 56)
        self.assertEqual(context.state.mood, "curious")
        self.assertEqual(context.state.trust, 21)
        self.assertEqual(context.state.attachment, 13)
        self.assertEqual(context.state.energy, 74)
        self.assertEqual(context.user_context.display_name, "Tester")
        self.assertEqual(context.user_context.formal_name, "Алексей")
        self.assertEqual(context.user_context.preferred_name, "Лёша")
        self.assertEqual(context.user_context.casual_name, "Лёха")
        self.assertEqual(context.user_context.vocative_name, "Лёш")
        self.assertEqual(context.user_context.age, 48)
        self.assertEqual(context.user_context.default_name, "Лёша")
        self.assertEqual(context.user_context.direct_address_name, "Лёш")
        self.assertEqual(context.user_context.address_policy, "preferred_by_relationship")
        self.assertTrue(context.user_context.name_usage_allowed)
        self.assertEqual(context.user_context.name_usage_reason, "available_but_optional")
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
        self.assertIsNone(context.scene_context.context_started_at)
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
        self.assertFalse(context.roleplay_context.has_roleplay_notation)
        self.assertEqual(context.roleplay_context.response_mode, "plain_chat")
        self.assertEqual(context.roleplay_context.action_segments, [])
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

    def test_memory_extraction_ignores_questions_without_durable_facts(self) -> None:
        memory = remember_user_message(
            self.db,
            self.character.id,
            "\u043a\u0430\u043a\u043e\u0435 \u044d\u0442\u043e \u0431\u0443\u0434\u0435\u0442 \u0447\u0438\u0441\u043b\u043e \u0431\u0443\u0434\u0443\u0449\u0430\u044f \u0441\u0443\u0431\u0431\u043e\u0442\u0430?",
        )

        self.assertIsNone(memory)

    def test_memory_extraction_normalizes_name_and_location_facts(self) -> None:
        name = remember_user_message(self.db, self.character.id, "\u043c\u0435\u043d\u044f \u0437\u043e\u0432\u0443\u0442 \u041b\u0435\u0445\u0430")
        born = remember_user_message(self.db, self.character.id, "\u044f \u0440\u043e\u0434\u0438\u043b\u0441\u044f \u0432 \u0423\u0445\u0442\u0435")
        lived = remember_user_message(
            self.db,
            self.character.id,
            "\u0434\u043e 17 \u043b\u0435\u0442 \u044f \u0436\u0438\u043b \u0432 \u0433\u043e\u0440\u043e\u0434\u0435 \u0423\u0445\u0442\u0430",
        )

        self.assertEqual(name.content, "\u0438\u043c\u044f \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f \u041b\u0435\u0445\u0430")
        self.assertEqual(name.importance, 3)
        self.assertEqual(born.content, "\u043c\u0435\u0441\u0442\u043e \u0440\u043e\u0436\u0434\u0435\u043d\u0438\u044f \u0423\u0445\u0442\u0435")
        self.assertEqual(born.memory_type, "life_event")
        self.assertEqual(
            lived.content,
            "\u043c\u0435\u0441\u0442\u043e \u0436\u0438\u0442\u0435\u043b\u044c\u0441\u0442\u0432\u0430 \u0434\u043e 17 \u043b\u0435\u0442 \u0423\u0445\u0442\u0430",
        )

    def test_memory_extraction_updates_existing_identity_fact(self) -> None:
        first = remember_user_message(self.db, self.character.id, "\u043c\u0435\u043d\u044f \u0437\u043e\u0432\u0443\u0442 \u041b\u0435\u0445\u0430")
        self.db.commit()
        second = remember_user_message(self.db, self.character.id, "\u0437\u043e\u0432\u0438 \u043c\u0435\u043d\u044f \u0410\u043b\u0435\u043a\u0441\u0435\u0439")
        self.db.commit()

        memories = self.db.query(Memory).filter(Memory.character_id == self.character.id).all()

        self.assertEqual(first.id, second.id)
        self.assertEqual(second.content, "\u0438\u043c\u044f \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f \u0410\u043b\u0435\u043a\u0441\u0435\u0439")
        self.assertEqual(len(memories), 1)

    def test_memory_update_endpoint_edits_content_type_and_importance(self) -> None:
        memory = Memory(
            character_id=self.character.id,
            memory_type="user_fact",
            content="old memory",
            importance=2,
        )
        self.db.add(memory)
        self.db.commit()
        memory_id = memory.id

        def override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        try:
            client = TestClient(app)
            response = client.patch(
                f"/memories/{memory_id}",
                json={
                    "memory_type": "preference",
                    "content": "updated memory",
                    "importance": 9,
                },
            )
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["memory_type"], "preference")
        self.assertEqual(payload["content"], "updated memory")
        self.assertEqual(payload["importance"], 5)

    def test_state_update_logic_is_stable_and_capped(self) -> None:
        self.character.state.trust_level = 100
        self.character.state.attachment_level = 99
        self.character.state.energy_level = 0

        state = update_state_after_message(self.character, "I love this, thank you :)")

        self.assertEqual(state.mood, "warm")
        self.assertEqual(state.trust_level, 100)
        self.assertEqual(state.attachment_level, 100)
        self.assertGreaterEqual(state.energy_level, 0)
        self.assertLessEqual(state.energy_level, 3)

    def test_state_engine_detects_conflict_and_smileys(self) -> None:
        conflict = analyze_user_message("Ты перепутал мое имя, не называй меня так")
        smile = analyze_user_message("Спасибо, мне хорошо :)")

        self.assertEqual(conflict.mood, "guarded")
        self.assertLess(conflict.trust_delta, 0)
        self.assertEqual(smile.mood, "warm")
        self.assertGreater(smile.trust_delta, 0)

    def test_state_engine_uses_stronger_balanced_deltas(self) -> None:
        conflict = analyze_user_message("Ты ошибся и не понял меня")
        negative = analyze_user_message("Мне грустно и одиноко")
        affection = analyze_user_message("Я скучаю и обнимаю тебя")
        positive = analyze_user_message("Спасибо, это класс :) ")
        question = analyze_user_message("Как ты? Что думаешь?")

        self.assertLessEqual(conflict.trust_delta, -2)
        self.assertLessEqual(conflict.attachment_delta, -1)
        self.assertLessEqual(conflict.energy_delta, -2)
        self.assertGreaterEqual(negative.attachment_delta, 1)
        self.assertLessEqual(negative.energy_delta, -2)
        self.assertGreaterEqual(affection.trust_delta, 1)
        self.assertGreaterEqual(affection.attachment_delta, 3)
        self.assertGreaterEqual(affection.energy_delta, 0)
        self.assertGreaterEqual(positive.trust_delta, 2)
        self.assertGreaterEqual(positive.attachment_delta, 1)
        self.assertGreaterEqual(positive.energy_delta, 1)
        self.assertGreaterEqual(question.trust_delta, 1)
        self.assertGreaterEqual(question.energy_delta, 0)

    def test_language_robustness_detects_slang_smileys_and_typos(self) -> None:
        signal = analyze_language_robustness("Сорян, щас норм вайб :)")

        self.assertTrue(signal.has_colloquial_language)
        self.assertEqual(signal.slang_terms["сорян"], "sorry, informal")
        self.assertEqual(signal.slang_terms["вайб"], "mood or atmosphere")
        self.assertEqual(signal.smileys[":)"], "friendly warmth or a light smile")
        self.assertEqual(signal.typo_hints["щас"], "сейчас")
        self.assertIn("Do not correct", signal.guidance)
        self.assertNotIn("((", analyze_language_robustness("((OOC: пауза))").smileys)
        self.assertIn("((", analyze_language_robustness("Мне грустно ((").smileys)

    def test_roleplay_protocol_detects_mixed_notation_and_ooc_only(self) -> None:
        mixed = analyze_roleplay_notation(
            "Привет. *сажусь рядом* ~надеюсь, он не заметил~ "
            "[сцена: за окном начинается дождь] ((OOC: без смены локации))"
        )
        ooc_only = analyze_roleplay_notation("((OOC: давай остановим *сцену*))")
        plain = analyze_roleplay_notation("Привет, как ты?")

        self.assertTrue(mixed.has_roleplay_notation)
        self.assertEqual(mixed.response_mode, "mirror_roleplay")
        self.assertEqual(mixed.action_segments, ["сажусь рядом"])
        self.assertEqual(mixed.thought_segments, ["надеюсь, он не заметил"])
        self.assertEqual(mixed.scene_notes, ["за окном начинается дождь"])
        self.assertEqual(mixed.ooc_notes, ["без смены локации"])
        self.assertEqual(ooc_only.response_mode, "ooc_only")
        self.assertEqual(ooc_only.ooc_notes, ["давай остановим *сцену*"])
        self.assertEqual(ooc_only.action_segments, [])
        self.assertFalse(plain.has_roleplay_notation)
        self.assertEqual(plain.response_mode, "plain_chat")

    def test_orchestrator_context_includes_detected_roleplay_segments(self) -> None:
        context = build_orchestrator_context(
            self.db,
            self.character,
            "*подхожу к окну* ~мне тревожно~ [scene: дождь усиливается]",
        )

        self.assertTrue(context.roleplay_context.has_roleplay_notation)
        self.assertEqual(context.roleplay_context.response_mode, "mirror_roleplay")
        self.assertEqual(context.roleplay_context.action_segments, ["подхожу к окну"])
        self.assertEqual(context.roleplay_context.thought_segments, ["мне тревожно"])
        self.assertEqual(context.roleplay_context.scene_notes, ["дождь усиливается"])

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
        self.assertEqual(payload["profile"]["warmth"], 82)
        self.assertEqual(payload["profile"]["initiative"], 68)
        self.assertEqual(payload["state"]["mood"], "curious")
        self.assertEqual(payload["user_context"]["city"], "Moscow")
        self.assertEqual(payload["user_context"]["timezone"], "Europe/Moscow")
        self.assertEqual(payload["roleplay_context"]["response_mode"], "plain_chat")
        self.assertEqual(payload["user_context"]["preferred_name"], "Лёша")
        self.assertEqual(payload["user_context"]["vocative_name"], "Лёш")
        self.assertEqual(payload["user_context"]["age"], 48)
        self.assertEqual(payload["scene_context"]["presence_mode"], "remote_chat")
        self.assertEqual(payload["scene_context"]["location_name"], "Private chat")
        self.assertEqual(payload["world_state"]["location_type"], "remote_chat")
        self.assertIn("language_context", payload)
        self.assertFalse(payload["language_context"]["has_colloquial_language"])
        self.assertEqual(set(payload["memory"].keys()), {"user_fact", "preference", "life_event", "relationship_note", "system_note"})
        self.assertEqual(payload["recent_messages"][0]["content"], "hello")
        self.assertEqual(payload["current_user_message"], "endpoint message")

    def test_companion_context_returns_memory_meta(self) -> None:
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
            response = client.get(f"/chat/{self.character.id}/context")
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["memory_meta"]["total_count"], 5)
        self.assertEqual(payload["memory_meta"]["visible_count"], 5)
        self.assertEqual(payload["memory_meta"]["visible_limit"], 8)
        self.assertEqual(payload["memory_meta"]["extraction_mode"], "rule_based")
        self.assertEqual(payload["memory_meta"]["counts_by_category"]["preference"], 1)
        self.assertIn("local rules", payload["memory_meta"]["note"])
        self.assertEqual(payload["user_context"]["formal_name"], "Алексей")
        self.assertEqual(payload["user_context"]["preferred_name"], "Лёша")

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
                    "warmth": 85,
                    "initiative": 70,
                    "playfulness": 35,
                    "directness": 60,
                    "emotionality": 75,
                    "rationality": 55,
                },
            )
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        character_id = response.json()["id"]
        scene = self.db.scalar(select(CharacterScene).where(CharacterScene.character_id == character_id))
        self.assertIsNotNone(scene)
        self.assertEqual(scene.presence_mode, "remote_chat")
        profile = self.db.scalar(select(CharacterProfile).where(CharacterProfile.character_id == character_id))
        self.assertIsNotNone(profile)
        self.assertEqual(response.json()["warmth"], 85)
        self.assertEqual(profile.initiative, 70)
        self.assertEqual(profile.playfulness, 35)

    def test_character_settings_can_be_updated_for_existing_character(self) -> None:
        def override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        try:
            client = TestClient(app)
            response = client.patch(
                f"/characters/{self.character.id}",
                json={
                    "relationship_mode": "colleague",
                    "personality_description": "Calm but curious",
                    "communication_style": "Direct and practical",
                    "warmth": 40,
                    "initiative": 80,
                    "playfulness": 20,
                    "directness": 90,
                    "emotionality": 30,
                    "rationality": 85,
                },
            )
            invalid_response = client.patch(f"/characters/{self.character.id}", json={"warmth": 101})
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["relationship_mode"], "colleague")
        self.assertEqual(payload["personality_description"], "Calm but curious")
        self.assertEqual(payload["communication_style"], "Direct and practical")
        self.assertEqual(payload["warmth"], 40)
        self.assertEqual(payload["initiative"], 80)
        self.assertEqual(payload["rationality"], 85)
        self.assertEqual(invalid_response.status_code, 422)

        self.db.expire_all()
        updated_character = self.db.get(Character, self.character.id)
        self.assertEqual(updated_character.relationship_mode, "colleague")
        self.assertEqual(updated_character.profile.directness, 90)
        self.assertEqual(updated_character.profile.emotionality, 30)

    def test_user_profile_can_be_updated_and_cleared(self) -> None:
        def override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        try:
            client = TestClient(app)
            response = client.patch(
                "/users/profile",
                json={
                    "character_id": self.character.id,
                    "display_name": "Алексей",
                    "formal_name": "Алексей Иванович",
                    "preferred_name": "Лёша",
                    "casual_name": "",
                    "vocative_name": "Лёш",
                    "age": 49,
                    "city": "Ухта",
                    "country": "Россия",
                    "timezone": "",
                    "language": "ru",
                },
            )
            invalid_response = client.patch(
                "/users/profile",
                json={"character_id": self.character.id, "age": 121},
            )
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["formal_name"], "Алексей Иванович")
        self.assertEqual(payload["preferred_name"], "Лёша")
        self.assertEqual(payload["casual_name"], "")
        self.assertEqual(payload["vocative_name"], "Лёш")
        self.assertEqual(payload["age"], 49)
        self.assertEqual(payload["city"], "Ухта")
        self.assertEqual(payload["timezone"], "Europe/Moscow")
        self.assertEqual(invalid_response.status_code, 422)

        self.db.expire_all()
        updated_user = self.db.get(User, self.character.user_id)
        self.assertEqual(updated_user.formal_name, "Алексей Иванович")
        self.assertEqual(updated_user.age, 49)

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
        self.assertIn("user_name: Лёша", prompt.system)
        self.assertIn("relationship_mode: friend", prompt.system)
        self.assertIn("user_city: Moscow", prompt.system)
        self.assertIn("user_country: Russia", prompt.system)
        self.assertIn("user_timezone: Europe/Moscow", prompt.system)
        self.assertIn("user_default_name: Лёша", prompt.system)
        self.assertIn("user_direct_address_name: Лёш", prompt.system)
        self.assertIn("user_address_policy: preferred_by_relationship", prompt.system)
        self.assertIn("user_name_usage_allowed_this_turn: True", prompt.system)
        self.assertIn("user_name_usage_reason: available_but_optional", prompt.system)
        self.assertIn("user_age: 48", prompt.system)
        self.assertIn("exact_current_user_local_date:", prompt.system)
        self.assertIn("current_user_weekday:", prompt.system)
        self.assertIn("current_user_time_of_day:", prompt.system)
        self.assertIn("current_user_daylight_context:", prompt.system)
        self.assertIn("presence_mode: remote_chat", prompt.system)
        self.assertIn("location_name: Private chat", prompt.system)
        self.assertIn("scene_time_description: not specified", prompt.system)
        self.assertIn("scene_context_started_at:", prompt.system)
        self.assertIn("This Scene context is the active episode", prompt.system)
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
        self.assertIn("Personality equalizer (continuous values from 0 to 100):", prompt.system)
        self.assertIn("warmth: 82", prompt.system)
        self.assertIn("initiative: 68", prompt.system)
        self.assertIn("playfulness: 37", prompt.system)
        self.assertIn("directness: 61", prompt.system)
        self.assertIn("emotionality: 74", prompt.system)
        self.assertIn("rationality: 56", prompt.system)
        self.assertIn("Apply all traits together as continuous tendencies", prompt.system)
        self.assertIn("the equalizer value controls behavior", prompt.system)
        self.assertIn("shape word choice, initiative, humor", prompt.system)
        self.assertIn("Never announce or recite personality trait names", prompt.system)
        self.assertIn("Express warmth and initiative according to the configured personality traits", prompt.system)
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
        self.assertIn("User knowledge guardrails:", prompt.system)
        self.assertIn("Treat a fact about the user as known only", prompt.system)
        self.assertIn("Never imply that the user previously mentioned", prompt.system)
        self.assertIn("Never transfer details from the character's persona", prompt.system)
        self.assertIn("Use names sparingly", prompt.system)
        self.assertIn("back-to-back routine replies", prompt.system)
        self.assertIn("orchestrator has already selected names", prompt.system)
        self.assertIn("normal and preferred behavior is to reply without using the user's name", prompt.system)
        self.assertIn("a name is merely available, never required", prompt.system)
        self.assertIn("do not justify repeating it more often", prompt.system)
        self.assertIn("Treat user_age as known only when it is explicitly set", prompt.system)
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
        self.assertIn("finished shared scene describe past experience only", prompt.system)
        self.assertIn("Old-scene words such as today, tomorrow", prompt.system)
        self.assertIn("the user is currently present at user_position", prompt.system)
        self.assertIn("scene_time_description is specified", prompt.system)
        self.assertIn("Do not invent a different place", prompt.system)
        self.assertIn("If the user asks where you are", prompt.system)
        self.assertIn("Never output tool calls", prompt.system)
        self.assertIn("<tool_call>", prompt.system)
        self.assertIn("Response length contract (high priority)", prompt.system)
        self.assertIn("Choose the response length from the current conversational need", prompt.system)
        self.assertIn("Distinguish a brief social check-in from an invitation to introspect", prompt.system)
        self.assertIn("'как ты?', 'как дела?', 'ты в порядке?'", prompt.system)
        self.assertIn("Answer directly in one natural sentence or at most two", prompt.system)
        self.assertIn("'что ты чувствуешь?', 'что у тебя внутри?'", prompt.system)
        self.assertIn("Answer more openly in about 3-6 sentences", prompt.system)
        self.assertIn("Do not reduce the answer to a mood label or state number", prompt.system)
        self.assertIn("reply in 1-3 concise sentences", prompt.system)
        self.assertIn("stay under about 120 words", prompt.system)
        self.assertIn("under about 180 words", prompt.system)
        self.assertIn("one complete installment of about 120-180 words", prompt.system)
        self.assertIn("'подлиннее' never mean writing up to the technical limit", prompt.system)
        self.assertIn("continue across conversational turns", prompt.system)
        self.assertIn("A simple turn stays short even when personality emotionality", prompt.system)
        self.assertIn("do not write up to the 500-token ceiling", prompt.system)
        self.assertIn("Understand slang, smileys, typos", prompt.system)
        self.assertIn("Do not lecture the user about slang or spelling", prompt.system)
        self.assertIn("Roleplay communication protocol:", prompt.system)
        self.assertIn("detected_response_mode: plain_chat", prompt.system)
        self.assertIn("Physical actions use *action*", prompt.system)
        self.assertIn("private thoughts use ~thought~", prompt.system)
        self.assertIn("Out-of-character notes use ((OOC: note))", prompt.system)
        self.assertIn("Never write, decide, or invent the user's speech", prompt.system)
        self.assertIn("It never changes presence_mode", prompt.system)
        self.assertIn("reply only as ((OOC: ...))", prompt.system)
        self.assertIn("Recent messages belong to the current scene context only", prompt.system)
        self.assertEqual([message.content for message in prompt.messages], ["hello", "hi", "current test message"])

    def test_prompt_builder_ignores_legacy_character_specific_user_name(self) -> None:
        self.character.profile.user_nickname = "Legacy Alias"
        self.character.user.display_name = "Global Profile Name"
        self.character.user.formal_name = ""
        self.character.user.preferred_name = ""
        self.character.user.casual_name = ""
        self.character.user.vocative_name = ""
        self.db.commit()

        context = build_orchestrator_context(self.db, self.character, "hello")
        prompt = build_provider_prompt(context)

        self.assertIn("user_name: the user", prompt.system)
        self.assertIn("do not invent a name for the user", prompt.system)
        self.assertIn("do not address the user by user_display_name", prompt.system)

    def test_prompt_builder_uses_explicit_preferred_name_without_inventing_forms(self) -> None:
        self.character.profile.user_nickname = ""
        self.character.user.formal_name = "Алексей"
        self.character.user.preferred_name = "Лёша"
        self.character.user.casual_name = ""
        self.character.user.vocative_name = "Лёш"
        self.db.commit()

        context = build_orchestrator_context(self.db, self.character, "hello")
        prompt = build_provider_prompt(context)

        self.assertIn("user_name: Лёша", prompt.system)
        self.assertIn("user_default_name: Лёша", prompt.system)
        self.assertIn("user_direct_address_name: Лёш", prompt.system)

    def test_name_address_policy_follows_relationship_role(self) -> None:
        colleague = build_user_address_policy("colleague", "Алексей", "Лёша", "Лёш")
        friend = build_user_address_policy("friend", "Алексей", "Лёша", "Лёш")
        romantic = build_user_address_policy("romantic", "Алексей", "Лёша", "Лёш")
        legacy_mentor = build_user_address_policy("mentor", "Алексей", "Лёша", "Лёш")

        self.assertEqual(colleague.default_name, "Алексей")
        self.assertEqual(colleague.direct_address_name, "Алексей")
        self.assertEqual(colleague.policy, "formal_by_relationship")
        self.assertEqual(friend.default_name, "Лёша")
        self.assertEqual(friend.direct_address_name, "Лёш")
        self.assertEqual(romantic.direct_address_name, "Лёш")
        self.assertEqual(legacy_mentor.default_name, "Алексей")

        no_vocative = build_user_address_policy("relative", "Алексей", "Лёша", "")
        self.assertEqual(no_vocative.direct_address_name, "Лёша")

    def test_name_usage_has_cooldown_but_allows_explicit_request(self) -> None:
        policy = build_user_address_policy("friend", "Алексей", "Лёша", "Лёш")
        recent_messages = [
            ("user", "Привет"),
            ("assistant", "Привет, Лёш. Рад тебя видеть."),
            ("user", "Как дела?"),
        ]

        cooldown = decide_name_usage("Расскажи, как дела", recent_messages, policy)
        explicit_request = decide_name_usage("Обратись ко мне по имени", recent_messages, policy)
        available = decide_name_usage(
            "Как дела?",
            [("assistant", "Рад тебя видеть.")] * 5,
            policy,
        )

        self.assertFalse(cooldown.allowed)
        self.assertEqual(cooldown.reason, "recent_name_cooldown")
        self.assertTrue(explicit_request.allowed)
        self.assertEqual(explicit_request.reason, "explicit_user_request")
        self.assertTrue(available.allowed)
        self.assertEqual(available.reason, "available_but_optional")
        self.assertTrue(contains_name("Привет, Леша.", "Лёша"))

    def test_prompt_suppresses_name_after_recent_use(self) -> None:
        self.db.add(
            Message(
                character_id=self.character.id,
                role="assistant",
                content="Привет, Лёш. Рад тебя видеть.",
            )
        )
        self.db.commit()

        context = build_orchestrator_context(self.db, self.character, "Как дела?")
        prompt = build_provider_prompt(context)

        self.assertFalse(context.user_context.name_usage_allowed)
        self.assertEqual(context.user_context.name_usage_reason, "recent_name_cooldown")
        self.assertIn("user_name: the user", prompt.system)
        self.assertIn("user_default_name: suppressed this turn", prompt.system)
        self.assertIn("user_name_usage_allowed_this_turn: False", prompt.system)

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

    def test_scene_update_keeps_context_while_new_scene_archives_and_cuts_it_off(self) -> None:
        scene = get_or_create_scene(self.db, self.character)
        scene.presence_mode = "same_place"
        scene.location_name = "Cinema"
        scene.location_description = "The user and character are watching The Matrix together."
        now = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=5)
        self.db.add_all(
            [
                Message(
                    character_id=self.character.id,
                    role="user",
                    content="Давай посмотрим Матрицу",
                    created_at=now,
                ),
                Message(
                    character_id=self.character.id,
                    role="assistant",
                    content="С удовольствием, беру попкорн",
                    created_at=now + timedelta(seconds=1),
                ),
            ]
        )
        self.db.commit()

        update_scene(
            self.db,
            self.character,
            SceneUpdate(
                character_id=self.character.id,
                presence_mode="same_place",
                location_name="Cinema hall",
                location_description="The film is still playing.",
                user_position="in a cinema seat",
                character_position="in the next seat",
            ),
        )
        continued_context = build_orchestrator_context(self.db, self.character, "продолжаем")
        self.assertEqual([message.content for message in continued_context.recent_messages], [
            "Давай посмотрим Матрицу",
            "С удовольствием, беру попкорн",
        ])

        new_scene = update_scene(
            self.db,
            self.character,
            SceneUpdate(
                character_id=self.character.id,
                presence_mode="same_place",
                location_name="Home sofa",
                location_description="Three days later, the user and character are relaxing at home.",
                time_description="three days later, in the evening",
                user_position="sitting on the sofa",
                character_position="sitting nearby",
                start_new_scene=True,
                previous_scene_summary="We went to the cinema together and watched The Matrix.",
            ),
        )

        self.assertIsNotNone(new_scene.context_started_at)
        self.assertEqual(new_scene.context_timestamp_basis, "utc")
        utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
        self.assertLess(abs(utc_now - new_scene.context_started_at), timedelta(seconds=5))
        new_context = build_orchestrator_context(self.db, self.character, "Как тебе тот фильм?")
        self.assertEqual(new_context.recent_messages, [])
        self.assertEqual(new_context.scene_context.time_description, "three days later, in the evening")
        scene_memories = new_context.memory["life_event"]
        self.assertEqual(len(scene_memories), 1)
        self.assertIn("Finished shared scene: Cinema hall", scene_memories[0].content)
        self.assertIn("watched The Matrix", scene_memories[0].content)
        self.assertIn("not the current physical scene", scene_memories[0].content)

        current_scene_message = Message(
            character_id=self.character.id,
            role="user",
            content="Мы уже дома на диване",
            created_at=new_scene.context_started_at + timedelta(seconds=1),
        )
        self.db.add(current_scene_message)
        self.db.commit()
        continued_new_context = build_orchestrator_context(self.db, self.character, "Помнишь кино?")
        self.assertEqual(
            [message.content for message in continued_new_context.recent_messages],
            ["Мы уже дома на диване"],
        )

    def test_new_scene_memory_falls_back_to_scene_and_recent_messages(self) -> None:
        scene = get_or_create_scene(self.db, self.character)
        scene.location_name = "Movie night"
        scene.location_description = "The user and character are choosing a film together."
        self.db.add_all(
            [
                Message(character_id=self.character.id, role="user", content="Включаем Матрицу"),
                Message(
                    character_id=self.character.id,
                    role="assistant",
                    content="Завтра снова придёшь за папкой",
                ),
            ]
        )
        self.db.commit()

        update_scene(
            self.db,
            self.character,
            SceneUpdate(
                character_id=self.character.id,
                presence_mode="same_place",
                location_name="Home",
                location_description="The next scene begins at home.",
                start_new_scene=True,
            ),
        )

        memory = self.db.scalar(
            select(Memory).where(Memory.character_id == self.character.id, Memory.memory_type == "life_event")
        )
        self.assertIsNotNone(memory)
        self.assertIn("Finished shared scene: Movie night", memory.content)
        self.assertIn("choosing a film together", memory.content)
        self.assertIn("user: Включаем Матрицу", memory.content)
        self.assertNotIn("Завтра снова придёшь за папкой", memory.content)
        self.assertIn("relative dates, plans, and unfinished actions must never be treated as current", memory.content)

    def test_timezone_can_be_inferred_from_city(self) -> None:
        self.assertEqual(infer_timezone("Ухта", "Россия"), "Europe/Moscow")
        self.assertEqual(infer_timezone("Novosibirsk", "Russia"), "Asia/Novosibirsk")

    def test_schema_sync_adds_personality_traits_to_existing_profile_table(self) -> None:
        legacy_engine = create_engine("sqlite://", poolclass=StaticPool)
        legacy_local_scene_start = datetime.now().replace(microsecond=0)
        with legacy_engine.begin() as connection:
            connection.execute(text("CREATE TABLE character_profiles (id VARCHAR PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE users (id VARCHAR PRIMARY KEY)"))
            connection.execute(
                text(
                    "CREATE TABLE character_scenes ("
                    "id VARCHAR PRIMARY KEY, character_id VARCHAR UNIQUE NOT NULL, "
                    "presence_mode VARCHAR NOT NULL DEFAULT 'remote_chat', "
                    "location_name VARCHAR NOT NULL DEFAULT 'Private chat', "
                    "location_description TEXT NOT NULL DEFAULT '', "
                    "user_position VARCHAR NOT NULL DEFAULT 'at their own place', "
                    "character_position VARCHAR NOT NULL DEFAULT 'at their own place', "
                    "context_started_at TIMESTAMP NULL, "
                    "updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO character_scenes "
                    "(id, character_id, context_started_at) "
                    "VALUES ('legacy-scene', 'legacy-character', :context_started_at)"
                ),
                {"context_started_at": legacy_local_scene_start},
            )

        ensure_dev_schema(legacy_engine)

        profile_columns = {column["name"] for column in inspect(legacy_engine).get_columns("character_profiles")}
        self.assertTrue(
            {"warmth", "initiative", "playfulness", "directness", "emotionality", "rationality"}.issubset(
                profile_columns
            )
        )
        user_columns = {column["name"] for column in inspect(legacy_engine).get_columns("users")}
        self.assertTrue(
            {"formal_name", "preferred_name", "casual_name", "vocative_name", "age"}.issubset(user_columns)
        )
        scene_columns = {column["name"] for column in inspect(legacy_engine).get_columns("character_scenes")}
        self.assertIn("context_started_at", scene_columns)
        self.assertIn("context_timestamp_basis", scene_columns)
        self.assertIn("time_description", scene_columns)
        with legacy_engine.connect() as connection:
            migrated_scene = connection.execute(
                text(
                    "SELECT context_started_at, context_timestamp_basis "
                    "FROM character_scenes WHERE id = 'legacy-scene'"
                )
            ).mappings().one()
        migrated_context_start = migrated_scene["context_started_at"]
        if isinstance(migrated_context_start, str):
            migrated_context_start = datetime.fromisoformat(migrated_context_start)
        self.assertEqual(
            migrated_context_start,
            legacy_local_timestamp_to_utc(legacy_local_scene_start),
        )
        self.assertEqual(migrated_scene["context_timestamp_basis"], "utc")
        legacy_engine.dispose()

    def test_legacy_finished_scene_memory_drops_assistant_plans(self) -> None:
        legacy_memory = (
            "Finished shared scene: Office. Scene-ending exchange: "
            "user: Я уже ушёл | assistant: Завтра, когда придёте, будет чай | "
            "user: Папку положите в сейф. This is shared past experience, not the current physical scene."
        )

        normalized = normalize_legacy_finished_scene_memory(legacy_memory)

        self.assertIn("user: Я уже ушёл", normalized)
        self.assertIn("user: Папку положите в сейф", normalized)
        self.assertNotIn("Завтра, когда придёте", normalized)
        self.assertIn("relative dates, plans, and unfinished actions", normalized)
        self.assertEqual(normalize_legacy_finished_scene_memory(normalized), normalized)

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

    def test_chat_export_and_clear_history_preserve_character_context(self) -> None:
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
            export_response = client.get(f"/chat/{self.character.id}/export")
            clear_response = client.delete(f"/chat/{self.character.id}")
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(export_response.status_code, 200)
        export_payload = export_response.json()
        self.assertEqual(export_payload["schema_version"], 1)
        self.assertTrue(export_payload["exported_at"])
        self.assertEqual(export_payload["character"]["id"], self.character.id)
        self.assertEqual(export_payload["character"]["name"], "Alice")
        self.assertEqual(export_payload["scene_context"]["character_id"], self.character.id)
        self.assertEqual(
            [(message["role"], message["content"]) for message in export_payload["messages"]],
            [("user", "hello"), ("assistant", "hi")],
        )
        self.assertEqual(len(export_payload["memories"]), 5)

        self.assertEqual(clear_response.status_code, 200)
        self.assertEqual(
            clear_response.json(),
            {
                "status": "cleared",
                "character_id": self.character.id,
                "deleted_messages": 2,
                "preserved_memories": 5,
            },
        )

        self.db.expire_all()
        self.assertEqual(
            self.db.scalars(select(Message).where(Message.character_id == self.character.id)).all(),
            [],
        )
        self.assertEqual(
            len(self.db.scalars(select(Memory).where(Memory.character_id == self.character.id)).all()),
            5,
        )
        preserved_character = self.db.get(Character, self.character.id)
        self.assertIsNotNone(preserved_character)
        self.assertIsNotNone(preserved_character.profile)
        self.assertIsNotNone(preserved_character.state)
        self.assertIsNotNone(preserved_character.scene)

    def test_delete_character_removes_character_data_but_keeps_shared_user(self) -> None:
        self.add_context_records()
        scene = get_or_create_scene(self.db, self.character)
        user_id = self.character.user_id
        character_id = self.character.id
        self.db.add_all(
            [
                MediaAsset(
                    character_id=character_id,
                    media_type="image",
                    url="mock://portrait",
                    prompt="portrait",
                ),
                IdentityReference(
                    character_id=character_id,
                    reference_type="face",
                    url="mock://reference",
                    prompt="identity reference",
                ),
            ]
        )
        self.db.commit()
        profile_id = self.character.profile.id
        state_id = self.character.state.id
        scene_id = scene.id

        def override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        try:
            client = TestClient(app)
            delete_response = client.delete(f"/characters/{character_id}")
            missing_response = client.get(f"/characters/{character_id}")
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(
            delete_response.json(),
            {"status": "deleted", "character_id": character_id},
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(missing_response.status_code, 404)

        self.db.expire_all()
        self.assertIsNone(self.db.get(Character, character_id))
        self.assertIsNone(self.db.get(CharacterProfile, profile_id))
        self.assertIsNone(self.db.get(CharacterState, state_id))
        self.assertIsNone(self.db.get(CharacterScene, scene_id))
        self.assertEqual(
            self.db.scalars(select(Message).where(Message.character_id == character_id)).all(),
            [],
        )
        self.assertEqual(
            self.db.scalars(select(Memory).where(Memory.character_id == character_id)).all(),
            [],
        )
        self.assertEqual(
            self.db.scalars(select(MediaAsset).where(MediaAsset.character_id == character_id)).all(),
            [],
        )
        self.assertEqual(
            self.db.scalars(
                select(IdentityReference).where(IdentityReference.character_id == character_id)
            ).all(),
            [],
        )
        self.assertIsNotNone(self.db.get(User, user_id))


if __name__ == "__main__":
    unittest.main()
