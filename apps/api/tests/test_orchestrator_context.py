import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.character import Character, CharacterProfile, CharacterState
from app.models.memory import Memory
from app.models.message import Message
from app.models.user import User
from app.services.character_engine import update_state_after_message
from app.services.memory_service import remember_user_message
from app.services.orchestrator_context import build_orchestrator_context


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
        user = User(email="test@example.com", display_name="Test User")
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

        state = update_state_after_message(self.character)

        self.assertEqual(state.mood, "attentive")
        self.assertEqual(state.trust_level, 100)
        self.assertEqual(state.attachment_level, 100)
        self.assertEqual(state.energy_level, 0)

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
        self.assertEqual(set(payload["memory"].keys()), {"user_fact", "preference", "life_event", "relationship_note", "system_note"})
        self.assertEqual(payload["recent_messages"][0]["content"], "hello")
        self.assertEqual(payload["current_user_message"], "endpoint message")


if __name__ == "__main__":
    unittest.main()
