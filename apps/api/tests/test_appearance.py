import unittest
from copy import deepcopy
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from PIL import Image

from app.database import Base, get_db
from app.main import app
from app.config import settings
from app.models.appearance import AppearanceCandidate, CharacterAppearance, ImageGenerationJob
from app.models.character import Character, CharacterProfile
from app.models.media_asset import MediaAsset
from app.models.user import User
from app.services.appearance_service import commit_appearance, stage_context
from app.providers.image_openrouter import GeneratedImage, ImageProviderError
from app.routers.appearance import get_image_session_factory
from app.schemas.appearance import AppearanceGenerate, AppearanceSettings
from app.services.image_generation import recover_interrupted_jobs, run_generation, submit_generation
from app.services.image_prompt_compiler import ImagePromptCompiler, ImagePromptCompilerError
from app.services.image_storage import resolve_image_file, save_image


class AppearanceTestCase(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.image_root = Path(temporary.name)
        storage_patch = patch("app.services.image_storage.IMAGE_STORAGE_ROOT", self.image_root)
        storage_patch.start()
        self.addCleanup(storage_patch.stop)
        config_patch = patch.multiple(settings, image_provider="disabled", image_api_key="", llm_api_key="",
                                      image_base_url="https://openrouter.ai/api/v1", image_model="black-forest-labs/flux.2-pro")
        config_patch.start()
        self.addCleanup(config_patch.stop)
        translations = {
            "рыжие": "vivid natural copper-red",
            "зеленые": "clear saturated green",
            "Веснушки и ямочки на щеках": "freckles and dimples",
            "Халат": "robe",
        }
        self.translator = Mock()
        self.translator.translate.side_effect = lambda values: {
            key: translations.get(value, value) for key, value in values.items()
        }
        compiler_patch = patch(
            "app.services.image_generation.get_image_prompt_compiler",
            return_value=ImagePromptCompiler(self.translator),
        )
        compiler_patch.start()
        self.addCleanup(compiler_patch.stop)
        output = BytesIO()
        Image.new("RGB", (16, 16), "navy").save(output, format="PNG")
        self.png = output.getvalue()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, autoflush=False)
        with self.sessions() as db:
            user = User(email="appearance@example.com", display_name="Tester")
            character = Character(user=user, name="Alice", gender="female")
            character.profile = CharacterProfile(voice_id="Leda")
            other = Character(user=user, name="Other", gender="male")
            db.add_all([character, other])
            db.commit()
            self.character_id, self.other_id = character.id, other.id

        def override_db():
            with self.sessions() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_image_session_factory] = lambda: self.sessions
        self.client = TestClient(app)
        self.path = f"/characters/{self.character_id}/appearance"

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def read(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def configure(self, settings=None, counts=None, revision=None):
        current = self.read()
        expected = current["revision"] if revision is None else revision
        try:
            values = AppearanceSettings.model_validate(current["settings"] if settings is None else settings).model_dump(exclude_none=True)
            count_values = current["counts"] if counts is None else counts
            if set(count_values) != {"face", "body", "clothing"} or any(type(value) is not int or not 1 <= value <= 3 for value in count_values.values()):
                raise ValueError
        except Exception:
            return SimpleNamespace(status_code=422)
        with self.sessions() as db:
            appearance = db.get(CharacterAppearance, self.character_id)
            if (appearance.revision if appearance else 0) != expected:
                return SimpleNamespace(status_code=409)
            if appearance is None:
                appearance = CharacterAppearance(character_id=self.character_id, settings={}, selections={})
                db.add(appearance)
            appearance.settings = values
            appearance.counts = dict(count_values)
            commit_appearance(db)
        return SimpleNamespace(status_code=200)

    def add_candidate(self, stage, *, owner=None, context=None, provider="test-provider"):
        # Test-only fixture. Production exposes no candidate-upload shortcut.
        with self.sessions() as db:
            appearance = db.get(CharacterAppearance, self.character_id)
            asset = MediaAsset(character_id=owner or self.character_id, media_type="image",
                               url=save_image(owner or self.character_id, self.png), provider=provider)
            db.add(asset)
            db.flush()
            candidate = AppearanceCandidate(character_id=owner or self.character_id, stage=stage,
                                            asset_id=asset.id, input_context=context or stage_context(appearance, stage))
            db.add(candidate)
            db.commit()
            return candidate.id

    def choose(self, stage, candidate):
        return self.client.post(f"{self.path}/select/{stage}", json={
            "expected_revision": self.read()["revision"], "candidate_id": candidate,
        })

    def complete(self):
        self.assertEqual(self.configure().status_code, 200)
        for stage in ("face", "body", "clothing"):
            self.assertEqual(self.choose(stage, self.add_candidate(stage)).status_code, 200)

    def publish(self, confirm=False):
        return self.client.post(f"{self.path}/publish", json={
            "expected_revision": self.read()["revision"], "confirm_gender_change": confirm,
        })

    def test_get_is_read_only_and_prefills_gender(self):
        result = self.read()
        self.assertEqual(result["settings"], {"gender": "female"})
        self.assertEqual(result["revision"], 0)
        self.assertFalse(result["generation_available"])
        with self.sessions() as db:
            self.assertIsNone(db.get(CharacterAppearance, self.character_id))

    def test_gender_only_persists_and_blanks_are_omitted(self):
        response = self.configure({"gender": "non_binary", "hair_color": "   ", "glasses": None})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.read()["settings"], {"gender": "non_binary"})
        self.assertEqual(self.read()["counts"], {"face": 1, "body": 1, "clothing": 1})
        with self.sessions() as db:
            self.assertEqual(db.get(Character, self.character_id).gender, "female")

    def test_validation_gender_counts_and_glasses(self):
        for settings in ({}, {"gender": "unspecified"}, {"gender": "female", "glasses": "false"},
                         {"gender": "female", "age": 2.5}, {"gender": "female", "unknown": "value"}):
            with self.subTest(settings=settings):
                self.assertEqual(self.configure(settings).status_code, 422)
        for count in (0, 4, True, 1.5):
            self.assertEqual(self.configure(counts={"face": count}).status_code, 422)
        for count in (1, 3):
            self.assertEqual(self.configure(counts={"face": count, "body": count, "clothing": count}).status_code, 200)
        self.assertEqual(self.configure({"gender": "female", "glasses": False}).status_code, 200)
        self.assertIs(self.read()["settings"]["glasses"], False)
        self.assertEqual(self.configure({"gender": "female", "appearance_type": "african"}).status_code, 200)
        self.assertEqual(self.read()["settings"]["appearance_type"], "african")
        self.assertEqual(self.configure({"gender": "female", "appearance_type": "unknown"}).status_code, 422)

    def test_stale_revision_is_rejected(self):
        self.assertEqual(self.configure().status_code, 200)
        self.assertEqual(self.configure({"gender": "male"}, revision=0).status_code, 409)
        self.assertEqual(self.read()["settings"]["gender"], "female")

    def test_database_version_check_catches_concurrent_sessions(self):
        self.configure()
        with self.sessions() as first, self.sessions() as second:
            a = first.get(CharacterAppearance, self.character_id)
            b = second.get(CharacterAppearance, self.character_id)
            a.settings = {"gender": "female", "hair_color": "red"}
            commit_appearance(first)
            b.settings = {"gender": "male"}
            with self.assertRaises(HTTPException) as caught:
                commit_appearance(second)
            self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.read()["settings"]["hair_color"], "red")

    def test_cross_character_and_wrong_stage_rejected(self):
        self.configure()
        other_candidate = self.add_candidate("face", owner=self.other_id)
        self.assertEqual(self.choose("face", other_candidate).status_code, 404)
        face = self.add_candidate("face")
        self.assertEqual(self.choose("body", face).status_code, 404)
        self.assertEqual(self.choose("invalid", face).status_code, 422)

    def test_mock_and_body_without_face_cannot_be_selected(self):
        self.configure()
        self.assertEqual(self.choose("face", self.add_candidate("face", provider="mock")).status_code, 409)
        self.assertEqual(self.choose("body", self.add_candidate("body")).status_code, 409)

    def test_new_face_preserves_independent_body_clothing_and_published(self):
        self.complete()
        self.assertEqual(self.publish().status_code, 200)
        before = self.read()
        self.assertEqual(self.choose("face", self.add_candidate("face")).status_code, 200)
        after = self.read()
        self.assertEqual(set(after["selections"]), {"face", "body", "clothing"})
        self.assertEqual(after["published"], before["published"])
        self.assertEqual(self.choose("body", before["selections"]["body"]).status_code, 200)
        self.assertEqual(self.publish().status_code, 200)

    def test_stage_parameters_do_not_delete_independent_selections(self):
        self.complete()
        before = self.read()
        settings = {**before["settings"], "clothing": "Халат"}
        self.assertEqual(self.configure(settings).status_code, 200)
        self.assertEqual(set(self.read()["selections"]), {"face", "body", "clothing"})
        self.assertEqual(self.configure({**settings, "body_type": "athletic"}).status_code, 200)
        self.assertEqual(set(self.read()["selections"]), {"face", "body", "clothing"})
        self.assertEqual(self.configure({**settings, "body_type": "athletic", "glasses": True}).status_code, 200)
        self.assertEqual(set(self.read()["selections"]), {"face", "body", "clothing"})
        old_face = next(c for c in self.read()["candidates"] if c["id"] == before["selections"]["face"])
        self.assertFalse(old_face["current"])

    def test_face_adjustment_choice_only_invalidates_body_and_later_stages(self):
        self.configure({"gender": "female", "body_type": "full", "face_adjustment": "allow"})
        face = self.add_candidate("face")
        self.assertEqual(self.choose("face", face).status_code, 200)
        body = self.add_candidate("body")
        self.assertEqual(self.choose("body", body).status_code, 200)
        self.assertEqual(self.configure({"gender": "female", "body_type": "full", "face_adjustment": "preserve"}).status_code, 200)
        candidates = {candidate["id"]: candidate for candidate in self.read()["candidates"]}
        self.assertTrue(candidates[face]["current"])
        self.assertFalse(candidates[body]["current"])

    def test_counts_and_reselecting_same_face_keep_selection(self):
        self.complete()
        before = self.read()
        self.assertEqual(self.configure(counts={"face": 3, "body": 2, "clothing": 1}).status_code, 200)
        self.assertEqual(self.choose("face", before["selections"]["face"]).status_code, 200)
        self.assertEqual(self.read()["selections"], before["selections"])

    def test_publish_is_coherent_idempotent_snapshot(self):
        self.complete()
        self.assertEqual(self.publish().status_code, 200)
        published = deepcopy(self.read()["published"])
        self.assertEqual(set(published["references"]), {"face", "body", "clothing"})
        self.assertEqual(published["version"], 1)
        self.assertEqual(self.publish().status_code, 200)
        self.assertEqual(self.read()["published"], published)

    def test_user_can_stop_and_publish_face_or_face_and_body(self):
        self.configure()
        self.assertEqual(self.choose("face", self.add_candidate("face")).status_code, 200)
        self.assertEqual(self.publish().status_code, 200)
        self.assertEqual(set(self.read()["published"]["references"]), {"face"})
        self.assertEqual(self.choose("body", self.add_candidate("body")).status_code, 200)
        self.assertEqual(self.publish().status_code, 200)
        published = self.read()["published"]
        self.assertEqual(set(published["references"]), {"face", "body"})
        self.assertEqual(published["version"], 2)
        self.configure({"gender": "female", "hair_color": "blue"})
        self.assertEqual(self.read()["published"], published)

    def test_gender_change_requires_confirmation_and_clears_incompatible_voice(self):
        self.configure({"gender": "male"})
        self.complete()
        self.assertEqual(self.publish().status_code, 409)
        with self.sessions() as db:
            self.assertEqual(db.get(Character, self.character_id).gender, "female")
        self.assertEqual(self.publish(confirm=True).status_code, 200)
        with self.sessions() as db:
            character = db.get(Character, self.character_id)
            self.assertEqual(character.gender, "male")
            self.assertEqual(character.profile.voice_id, "")

    def test_clear_chat_keeps_appearance_delete_character_removes_it(self):
        self.complete()
        self.publish()
        self.assertEqual(self.client.delete(f"/chat/{self.character_id}").status_code, 200)
        self.assertIsNotNone(self.read()["published"])
        self.assertEqual(self.client.delete(f"/characters/{self.character_id}").status_code, 200)
        self.assertEqual(self.client.get(self.path).status_code, 404)
        with self.sessions() as db:
            for model in (CharacterAppearance, AppearanceCandidate, MediaAsset):
                self.assertIsNone(db.scalar(select(model).where(model.character_id == self.character_id)))

    def test_image_endpoint_does_not_produce_placeholder(self):
        response = self.client.post("/media/image", json={"character_id": self.character_id, "prompt": "portrait"})
        self.assertEqual(response.status_code, 409)
        with self.sessions() as db:
            self.assertIsNone(db.scalar(select(MediaAsset)))

    def test_missing_character_is_404(self):
        self.assertEqual(self.client.get("/characters/missing/appearance").status_code, 404)
        self.assertEqual(self.client.put("/characters/missing/appearance", json={}).status_code, 405)

    def enable_images(self):
        patcher = patch.multiple(settings, image_provider="openrouter", llm_api_key="unit-test-key")
        patcher.start()
        self.addCleanup(patcher.stop)

    def submit_job(self, stage="face", *, request_id=None, retry_of=None, confirm_unknown_retry=False):
        current = self.read()
        with self.sessions() as db:
            payload = AppearanceGenerate(
                request_id=request_id or uuid4(), expected_revision=current["revision"],
                retry_of=retry_of, confirm_unknown_retry=confirm_unknown_retry,
                settings=None if retry_of else AppearanceSettings.model_validate(current["settings"]),
                count=None if retry_of else current["counts"][stage],
            )
            job, created = submit_generation(db, self.character_id, stage, payload)
            return job.id, created

    def fake_provider(self):
        provider = Mock()
        provider.generate.return_value = GeneratedImage(self.png, Decimal("0.03"))
        return provider

    def test_real_generation_route_schedules_and_persists_provider_output(self):
        self.enable_images()
        self.configure()
        request_id = str(uuid4())
        provider = self.fake_provider()
        with patch("app.services.image_generation.create_image_provider", return_value=provider):
            response = self.client.post(f"{self.path}/generate/face", json={
                "request_id": request_id, "expected_revision": self.read()["revision"],
                "settings": self.read()["settings"], "count": 1,
            })
        self.assertEqual(response.status_code, 202, response.text)
        state = self.read()
        self.assertEqual(state["jobs"][0]["status"], "completed")
        self.assertEqual(state["jobs"][0]["outputs"][0]["cost_usd"], "0.03")
        self.assertEqual(len(state["candidates"]), 1)
        candidate = state["candidates"][0]
        self.assertTrue(resolve_image_file(candidate["url"], self.character_id).is_file())
        self.assertEqual(self.choose("face", candidate["id"]).status_code, 200)
        provider.generate.assert_called_once()
        self.assertEqual(provider.generate.call_args.kwargs["references"], [])

    def test_first_generation_persists_parameters_without_draft_endpoint(self):
        self.enable_images()
        provider = self.fake_provider()
        with patch("app.services.image_generation.create_image_provider", return_value=provider):
            response = self.client.post(f"{self.path}/generate/face", json={
                "request_id": str(uuid4()), "expected_revision": 0, "count": 2,
                "settings": {"gender": "female", "face_details": "Веснушки и ямочки на щеках"},
            })
        self.assertEqual(response.status_code, 202, response.text)
        state = self.read()
        self.assertEqual(state["settings"]["face_details"], "Веснушки и ямочки на щеках")
        self.assertEqual(state["counts"]["face"], 2)
        self.assertEqual(provider.generate.call_count, 2)
        self.assertEqual(self.client.put(self.path, json={}).status_code, 405)

    def test_duplicate_submissions_and_worker_execution_charge_once(self):
        self.enable_images()
        self.configure()
        request_id = uuid4()
        job_id, created = self.submit_job(request_id=request_id)
        self.assertTrue(created)
        self.assertEqual(self.submit_job(request_id=request_id), (job_id, False))
        with self.assertRaises(HTTPException) as caught:
            self.submit_job()
        self.assertEqual(caught.exception.status_code, 409)
        provider = self.fake_provider()
        run_generation(job_id, self.sessions, provider)
        run_generation(job_id, self.sessions, provider)
        self.assertEqual(self.submit_job(request_id=request_id), (job_id, False))
        provider.generate.assert_called_once()

    def test_body_and_clothing_receive_canonical_references(self):
        self.enable_images()
        self.complete()
        provider = self.fake_provider()
        job_id, _ = self.submit_job("body")
        run_generation(job_id, self.sessions, provider)
        self.assertEqual(len(provider.generate.call_args.kwargs["references"]), 1)
        job_id, _ = self.submit_job("clothing")
        run_generation(job_id, self.sessions, provider)
        self.assertEqual(len(provider.generate.call_args.kwargs["references"]), 2)
        self.assertIn("reference 1 defines the face", provider.generate.call_args.kwargs["prompt"])

    def test_full_body_generation_requires_face_adjustment_choice(self):
        self.enable_images()
        self.configure({"gender": "female", "body_type": "full"})
        self.assertEqual(self.choose("face", self.add_candidate("face")).status_code, 200)
        response = self.client.post(f"{self.path}/generate/body", json={
            "request_id": str(uuid4()), "expected_revision": self.read()["revision"],
            "settings": self.read()["settings"], "count": 1,
        })
        self.assertEqual(response.status_code, 422)
        with self.sessions() as db:
            self.assertIsNone(db.scalar(select(ImageGenerationJob)))
        self.assertEqual(self.configure({"gender": "female", "body_type": "full", "face_adjustment": "allow"}).status_code, 200)
        job_id, _ = self.submit_job("body")
        with self.sessions() as db:
            job = db.get(ImageGenerationJob, job_id)
            self.assertEqual(job.input_context["settings"]["face_adjustment"], "allow")
            self.assertIn("subtly adjust facial fullness", job.prompt)

    def test_venice_pair_uses_only_latest_reference_and_keeps_openrouter_settings(self):
        self.configure({"gender": "female", "glasses": False, "hair_color": "рыжие", "eye_color": "зеленые"})
        self.complete()
        with patch.multiple(settings, image_provider="venice", venice_api_key="unit-test-venice-key"):
            state = self.read()
            self.assertTrue(state["generation_available"])
            self.assertEqual(state["image_model"], "qwen-image-3")
            self.assertEqual(state["image_edit_model"], "qwen-edit-uncensored")
            provider = self.fake_provider()
            face_job, _ = self.submit_job("face")
            run_generation(face_job, self.sessions, provider)
            self.assertEqual(provider.generate.call_args.kwargs["model"], "qwen-image-3")
            self.assertEqual(provider.generate.call_args.kwargs["references"], [])
            self.assertIn("eyeglasses", provider.generate.call_args.kwargs["negative_prompt"])
            self.assertNotIn("glasses", provider.generate.call_args.kwargs["prompt"])
            self.assertIn("vivid natural copper-red", provider.generate.call_args.kwargs["prompt"])
            self.assertIn("clear saturated green", provider.generate.call_args.kwargs["prompt"])
            body_job, _ = self.submit_job("body")
            run_generation(body_job, self.sessions, provider)
            self.assertEqual(provider.generate.call_args.kwargs["model"], "qwen-edit-uncensored")
            self.assertEqual(len(provider.generate.call_args.kwargs["references"]), 1)
            clothing_job, _ = self.submit_job("clothing")
            run_generation(clothing_job, self.sessions, provider)
            self.assertEqual(provider.generate.call_args.kwargs["model"], "qwen-edit-uncensored")
            self.assertEqual(len(provider.generate.call_args.kwargs["references"]), 1)
            self.assertIn("selected body image", provider.generate.call_args.kwargs["prompt"])
            self.assertIn("vivid natural copper-red", provider.generate.call_args.kwargs["prompt"])
            self.assertIn("clear saturated green", provider.generate.call_args.kwargs["prompt"])
            with self.sessions() as db:
                job = db.get(ImageGenerationJob, clothing_job)
                self.assertEqual(job.input_context["image_provider"], "venice")
                self.assertEqual(job.input_context["compiled_settings"]["hair_color"], "vivid natural copper-red")
                self.assertEqual(job.input_context["prompt_compiler_version"], 1)
                assets = db.scalars(select(MediaAsset).where(MediaAsset.provider.like("venice:%"))).all()
                self.assertEqual(len(assets), 3)

    def test_compiler_failure_starts_no_job_and_persists_no_settings(self):
        self.enable_images()
        self.translator.translate.side_effect = ImagePromptCompilerError("translation failed")
        response = self.client.post(f"{self.path}/generate/face", json={
            "request_id": str(uuid4()), "expected_revision": 0, "count": 1,
            "settings": {"gender": "female", "hair_color": "фиолетовые"},
        })
        self.assertEqual(response.status_code, 503)
        detail = response.json()["detail"]
        self.assertEqual(detail["error"], "image_prompt_compilation_failed")
        self.assertIn("не запускалась", detail["message"])
        with self.sessions() as db:
            self.assertIsNone(db.get(CharacterAppearance, self.character_id))
            self.assertIsNone(db.scalar(select(ImageGenerationJob)))

    def test_generation_requires_parameters_and_prior_references(self):
        self.enable_images()
        response = self.client.post(f"{self.path}/generate/face", json={"request_id": str(uuid4()), "expected_revision": 0})
        self.assertEqual(response.status_code, 422)
        self.configure()
        with self.assertRaises(HTTPException):
            self.submit_job("body")
        self.choose("face", self.add_candidate("face"))
        selected = next(c for c in self.read()["candidates"] if c["stage"] == "face")
        resolve_image_file(selected["url"], self.character_id).unlink()
        with self.assertRaises(HTTPException):
            self.submit_job("body")

    def test_partial_batch_retry_submits_only_missing_outputs(self):
        self.enable_images()
        self.configure(counts={"face": 3, "body": 1, "clothing": 1})
        job_id, _ = self.submit_job()
        provider = self.fake_provider()
        provider.generate.side_effect = [GeneratedImage(self.png, Decimal("0.03")), ImageProviderError("Rate limit")]
        run_generation(job_id, self.sessions, provider)
        state = self.read()
        self.assertEqual(state["jobs"][0]["status"], "partial")
        self.assertEqual([o["status"] for o in state["jobs"][0]["outputs"]], ["completed", "failed", "not_started"])
        self.assertEqual(provider.generate.call_count, 2)
        successful_id = state["candidates"][0]["id"]
        retry_id, _ = self.submit_job(retry_of=job_id)
        retry_provider = self.fake_provider()
        run_generation(retry_id, self.sessions, retry_provider)
        self.assertEqual(retry_provider.generate.call_count, 2)
        self.assertEqual(len(self.read()["candidates"]), 3)
        self.assertIn(successful_id, [c["id"] for c in self.read()["candidates"]])
        with self.assertRaises(HTTPException):
            self.submit_job(retry_of=job_id)

    def test_retry_reuses_compiled_prompt_without_translation(self):
        self.enable_images()
        self.configure({"gender": "female", "hair_color": "рыжие"})
        job_id, _ = self.submit_job()
        provider = self.fake_provider()
        provider.generate.side_effect = ImageProviderError("Rate limit")
        run_generation(job_id, self.sessions, provider)
        self.assertEqual(self.translator.translate.call_count, 1)
        retry_id, _ = self.submit_job(retry_of=job_id)
        self.assertEqual(self.translator.translate.call_count, 1)
        with self.sessions() as db:
            self.assertEqual(db.get(ImageGenerationJob, retry_id).prompt,
                             db.get(ImageGenerationJob, job_id).prompt)

    def test_unknown_outcome_requires_explicit_retry_confirmation(self):
        self.enable_images()
        self.configure()
        job_id, _ = self.submit_job()
        provider = self.fake_provider()
        provider.generate.side_effect = ImageProviderError("Timeout", unknown_outcome=True)
        run_generation(job_id, self.sessions, provider)
        self.assertEqual(self.read()["jobs"][0]["outputs"][0]["status"], "unknown")
        with self.assertRaises(HTTPException):
            self.submit_job(retry_of=job_id)
        retry_id, _ = self.submit_job(retry_of=job_id, confirm_unknown_retry=True)
        run_generation(retry_id, self.sessions, self.fake_provider())
        self.assertEqual(len(self.read()["candidates"]), 1)

    def test_restart_does_not_resubmit_requests(self):
        self.enable_images()
        self.configure(counts={"face": 2, "body": 1, "clothing": 1})
        job_id, _ = self.submit_job()
        with self.sessions() as db:
            job = db.get(ImageGenerationJob, job_id)
            job.status = "running"
            outputs = deepcopy(job.outputs)
            outputs[0]["status"] = "running"
            job.outputs = outputs
            db.commit()
            recover_interrupted_jobs(db)
        job = self.read()["jobs"][0]
        self.assertEqual(job["status"], "interrupted")
        self.assertEqual([item["status"] for item in job["outputs"]], ["unknown", "not_started"])
        provider = self.fake_provider()
        run_generation(job_id, self.sessions, provider)
        provider.generate.assert_not_called()

    def test_upstream_edit_during_generation_keeps_output_but_marks_it_stale(self):
        self.enable_images()
        self.configure()
        job_id, _ = self.submit_job()
        self.configure({"gender": "female", "hair_color": "blue"})
        run_generation(job_id, self.sessions, self.fake_provider())
        candidate = self.read()["candidates"][0]
        self.assertFalse(candidate["current"])
        self.assertEqual(self.choose("face", candidate["id"]).status_code, 409)

    def test_deletion_during_network_call_cannot_restore_files_or_rows(self):
        self.enable_images()
        self.configure()
        job_id, _ = self.submit_job()
        provider = self.fake_provider()

        def delete_while_waiting(**kwargs):
            response = self.client.delete(f"/characters/{self.character_id}")
            self.assertEqual(response.status_code, 200, response.text)
            return GeneratedImage(self.png, Decimal("0.03"))

        provider.generate.side_effect = delete_while_waiting
        run_generation(job_id, self.sessions, provider)
        self.assertEqual(list(self.image_root.rglob("*.png")), [])
        with self.sessions() as db:
            self.assertIsNone(db.get(ImageGenerationJob, job_id))
            self.assertIsNone(db.scalar(select(AppearanceCandidate)))

    def test_invalid_output_preserves_charge_and_has_no_candidate(self):
        self.enable_images()
        self.configure()
        job_id, _ = self.submit_job()
        provider = self.fake_provider()
        provider.generate.return_value = GeneratedImage(b"not-an-image", Decimal("0.03"))
        run_generation(job_id, self.sessions, provider)
        state = self.read()
        self.assertEqual(state["jobs"][0]["status"], "failed")
        self.assertEqual(state["jobs"][0]["outputs"][0]["cost_usd"], "0.03")
        self.assertEqual(state["candidates"], [])

    def test_three_outputs_make_three_individual_calls(self):
        self.enable_images()
        self.configure(counts={"face": 3, "body": 1, "clothing": 1})
        job_id, _ = self.submit_job()
        provider = self.fake_provider()
        run_generation(job_id, self.sessions, provider)
        self.assertEqual(provider.generate.call_count, 3)
        self.assertEqual(len(self.read()["candidates"]), 3)

    def test_paid_generation_is_disabled_without_configuration(self):
        self.configure()
        response = self.client.post(f"{self.path}/generate/face", json={
            "request_id": str(uuid4()), "expected_revision": self.read()["revision"],
            "settings": self.read()["settings"], "count": 1,
        })
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.read()["jobs"], [])

    def test_local_image_route_serves_generated_png(self):
        self.enable_images()
        self.configure()
        job_id, _ = self.submit_job()
        run_generation(job_id, self.sessions, self.fake_provider())
        url = self.read()["candidates"][0]["url"]
        media_mount = next(route for route in app.routes if getattr(route, "name", None) == "media-files")
        with patch.object(media_mount.app, "directory", str(self.image_root)), patch.object(media_mount.app, "all_directories", [str(self.image_root)]):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertTrue(response.content.startswith(b"\x89PNG"))

    def test_generation_job_does_not_appear_in_another_character(self):
        self.enable_images()
        self.configure()
        job_id, _ = self.submit_job()
        state = self.client.get(f"/characters/{self.other_id}/appearance").json()
        self.assertEqual(state["jobs"], [])
        self.assertEqual(state["candidates"], [])
        self.assertNotIn("unit-test-key", str(self.read()))
