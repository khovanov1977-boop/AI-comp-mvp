import json
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database import Base
from app.models.appearance import CharacterAppearance
from app.models.character import Character, CharacterState
from app.models.message import Message
from app.models.scene_image import SceneImageJob
from app.models.user import User
from app.providers.image_openrouter import GeneratedImage, ImageProviderError
from app.services.image_storage import save_image
from app.services.scene_image_generation import (
    is_photo_request, recover_interrupted_scene_images, run_scene_image, submit_scene_image,
)
from app.services.scene_image_prompt import CompiledSceneImagePrompt, SceneImagePromptCompiler


class SceneImagePromptTest(unittest.TestCase):
    def test_resolves_recent_clothing_and_latest_override_in_english(self):
        def handler(request):
            body = json.loads(request.content)
            self.assertEqual(body["models"][0], "current/model")
            source = json.loads(body["messages"][1]["content"])
            self.assertEqual(source["recent_dialogue"][-1]["content"], "Сижу пью чай в халате")
            self.assertIn("смени одежду на синее платье", source["latest_photo_request"])
            self.assertIn("highest priority", body["messages"][0]["content"])
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
                "location": "kitchen", "activity": "drinking tea", "clothing": "blue dress",
                "pose": "seated", "lighting": "warm daylight",
            })}}]})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)
        config = Settings(llm_base_url="https://openrouter.ai/api/v1", llm_api_key="test",
                          llm_model="current/model", image_prompt_models="backup/model")
        result = SceneImagePromptCompiler(config, client).compile(
            {"location_name": "kitchen"}, [{"role": "assistant", "content": "Сижу пью чай в халате"}],
            "Пришли фото, но сначала смени одежду на синее платье",
        )
        self.assertIn("Current activity: drinking tea", result.prompt)
        self.assertIn("Clothing: blue dress", result.prompt)
        self.assertLessEqual(len(result.prompt), 1500)

    def test_intent_requires_photo_request(self):
        self.assertTrue(is_photo_request("Пришли фото"))
        self.assertTrue(is_photo_request("Покажи фотографию, как пьешь чай"))
        self.assertFalse(is_photo_request("Я вчера видел твоё фото"))


class SceneImageJobTest(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        storage_patch = patch("app.services.image_storage.IMAGE_STORAGE_ROOT", Path(temporary.name))
        storage_patch.start()
        self.addCleanup(storage_patch.stop)
        config_patch = patch("app.services.scene_image_generation.image_configuration_error", return_value="")
        config_patch.start()
        self.addCleanup(config_patch.stop)
        image = BytesIO()
        Image.new("RGB", (16, 16), "blue").save(image, format="PNG")
        self.png = image.getvalue()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, autoflush=False)
        with self.sessions() as db:
            user = User(email="scene-image@example.com", display_name="Tester")
            character = Character(user=user, name="Ирина", gender="female")
            character.state = CharacterState()
            db.add(character)
            db.commit()
            self.character_id = character.id
            reference_url = save_image(character.id, self.png)
            db.add(CharacterAppearance(character_id=character.id, settings={}, selections={},
                                       published={"references": {"body": {"url": reference_url}}}))
            db.add(Message(character_id=character.id, role="assistant", content="Сижу пью чай в халате"))
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def compiler(self):
        compiler = Mock()
        compiler.compile.return_value = CompiledSceneImagePrompt(
            prompt="Edit the reference into the same person, drinking tea in a robe.",
            resolved={"activity": "drinking tea", "clothing": "robe"},
        )
        return compiler

    def test_one_paid_call_and_idempotent_submission(self):
        request_id = uuid4()
        compiler = self.compiler()
        with self.sessions() as db:
            character = db.get(Character, self.character_id)
            job, created = submit_scene_image(db, character, "Пришли фото", request_id, compiler)
            self.assertTrue(created)
            self.assertEqual(compiler.compile.call_args.args[1][-1]["content"], "Сижу пью чай в халате")
            duplicate, created = submit_scene_image(db, character, "Пришли фото", request_id, compiler)
            self.assertFalse(created)
            self.assertEqual(duplicate.id, job.id)
            with self.assertRaises(HTTPException):
                submit_scene_image(db, character, "Покажи другое фото", uuid4(), compiler)
        provider = Mock()
        provider.generate.return_value = GeneratedImage(data=self.png)
        run_scene_image(str(request_id), self.sessions, provider)
        run_scene_image(str(request_id), self.sessions, provider)
        provider.generate.assert_called_once()
        with self.sessions() as db:
            job = db.get(SceneImageJob, str(request_id))
            message = db.get(Message, job.assistant_message_id)
            self.assertEqual(job.status, "completed")
            self.assertEqual(message.image_generation_status, "completed")
            self.assertTrue(message.image_url.startswith("/media-files/"))

    def test_ambiguous_provider_failure_never_retries(self):
        request_id = uuid4()
        with self.sessions() as db:
            submit_scene_image(db, db.get(Character, self.character_id), "Пришли фото", request_id, self.compiler())
        provider = Mock()
        provider.generate.side_effect = ImageProviderError("connection lost", unknown_outcome=True)
        run_scene_image(str(request_id), self.sessions, provider)
        run_scene_image(str(request_id), self.sessions, provider)
        provider.generate.assert_called_once()
        with self.sessions() as db:
            self.assertEqual(db.get(SceneImageJob, str(request_id)).status, "unknown")

    def test_restart_marks_queued_without_sending(self):
        request_id = uuid4()
        with self.sessions() as db:
            submit_scene_image(db, db.get(Character, self.character_id), "Пришли фото", request_id, self.compiler())
            recover_interrupted_scene_images(db)
            self.assertEqual(db.get(SceneImageJob, str(request_id)).status, "not_started")
        provider = Mock()
        run_scene_image(str(request_id), self.sessions, provider)
        provider.generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
