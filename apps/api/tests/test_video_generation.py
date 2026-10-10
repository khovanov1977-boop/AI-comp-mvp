import base64
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.appearance import CharacterAppearance
from app.models.character import Character
from app.models.message import Message
from app.models.user import User
from app.models.video import VideoJob
from app.models.beta_usage import BetaUsage
from app.providers.video_venice import QueuedVideo, VeniceVideoError, VeniceVideoProvider
from app.schemas.video import VideoQuoteRequest, VideoRequest
from app.services.image_storage import save_image
from app.services.video_generation import quote_video, recover_interrupted_videos, run_video, submit_video
from app.services.video_prompt import VideoPromptError


class VideoGenerationTest(unittest.TestCase):
    def setUp(self):
        self.translator = Mock()
        self.translator.translate.side_effect = lambda values: {
            key: "The character acts and says:" for key in values
        }
        translator_patch = patch("app.services.video_generation.VeniceVideoSceneTranslator",
                                 return_value=self.translator)
        translator_patch.start()
        self.addCleanup(translator_patch.stop)
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        for target in ("app.services.image_storage.IMAGE_STORAGE_ROOT", "app.services.video_storage.IMAGE_STORAGE_ROOT"):
            storage_patch = patch(target, Path(temporary.name))
            storage_patch.start()
            self.addCleanup(storage_patch.stop)
        image = BytesIO()
        Image.new("RGB", (512, 768), "blue").save(image, format="PNG")
        self.png = image.getvalue()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, autoflush=False)
        with self.sessions() as db:
            user = User(email="video@example.com", display_name="Tester")
            character = Character(user=user, name="Ирина", gender="female")
            db.add(character)
            db.commit()
            self.character_id = character.id
            self.face = save_image(character.id, self.png)
            self.body = save_image(character.id, self.png)
            photo = Message(character_id=character.id, role="assistant", content="Вот фото.",
                            message_type="image", image_url=self.body, image_generation_status="completed")
            db.add(photo)
            db.add(CharacterAppearance(character_id=character.id, settings={}, selections={},
                                       published={"references": {"face": {"url": self.face}, "body": {"url": self.body}}}))
            db.commit()
            self.photo_id = photo.id

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def provider(self):
        provider = Mock()
        provider.available_models.return_value = {
            "wan-2-7-enhanced-image-to-video", "wan-2-7-reference-to-video",
            "wan-3-0-reference-to-video",
        }
        provider.quote.side_effect = lambda model, *_, **__: "0.33" if model == "wan-3-0-reference-to-video" else "0.64"
        provider.queue.return_value = QueuedVideo("wan-3-0-reference-to-video", "venice-queue-1")
        provider.retrieve.return_value = ("completed", b"\x00\x00\x00\x18ftypisom00000000")
        return provider

    def request(self, mode="animate_photo", **changes):
        data = dict(request_id=uuid4(), mode=mode, prompt='Персонаж поворачивается и говорит: "Привет!"',
                    source_message_id=self.photo_id if mode == "animate_photo" else None,
                    resolution="480p", accepted_quote_usd="0.33")
        data.update(changes)
        return VideoRequest(**data)

    def test_catalog_selects_wan_reference_and_quotes_before_submit(self):
        provider = self.provider()
        result = quote_video(VideoQuoteRequest(mode="reference_video", resolution="480p"), provider)
        self.assertEqual(result.model, "wan-3-0-reference-to-video")
        self.assertEqual(result.price_usd, "0.33")
        provider.quote.assert_called_once_with("wan-3-0-reference-to-video", "5s", "480p",
                                               aspect_ratio="adaptive", audio=True)
        provider.quote.reset_mock()
        animation = quote_video(VideoQuoteRequest(mode="animate_photo", resolution="480p"), provider)
        self.assertEqual(animation.model, result.model)
        self.assertEqual(animation.price_usd, "0.33")
        provider.quote.assert_called_once_with("wan-3-0-reference-to-video", "5s", "480p",
                                               aspect_ratio="adaptive", audio=True)

    def test_photo_animation_uses_selected_message_and_queues_once(self):
        provider = self.provider()
        payload = self.request()
        with self.sessions() as db:
            job, created = submit_video(db, self.character_id, payload, provider)
            self.assertTrue(created)
            duplicate, created = submit_video(db, self.character_id, payload, provider)
            self.assertFalse(created)
            self.assertEqual(duplicate.id, job.id)
        run_video(str(payload.request_id), self.sessions, provider)
        run_video(str(payload.request_id), self.sessions, provider)
        provider.queue.assert_called_once()
        queued_payload = provider.queue.call_args.args[0]
        self.assertEqual(len(queued_payload["reference_image_urls"]), 1)
        self.assertTrue(queued_payload["reference_image_urls"][0].startswith("data:image/jpeg;base64,"))
        self.assertNotIn("image_url", queued_payload)
        self.assertEqual(queued_payload["aspect_ratio"], "adaptive")
        self.assertIs(queued_payload["audio"], True)
        self.assertEqual(queued_payload["resolution"], "480p")
        self.assertEqual(queued_payload["prompt"], 'The character acts and says: "Привет!"')
        with self.sessions() as db:
            job = db.get(VideoJob, str(payload.request_id))
            message = db.get(Message, job.assistant_message_id)
            self.assertEqual(job.status, "completed")
            self.assertTrue(message.video_url.endswith(".mp4"))
            self.assertEqual(message.video_job_id, job.id)

    def test_beta_video_cap_preserves_idempotent_retry(self):
        provider = self.provider()
        payload = self.request()
        with patch("app.services.beta_limits.settings.beta_max_video_requests", 1):
            with self.sessions() as db:
                first, created = submit_video(db, self.character_id, payload, provider)
                self.assertTrue(created)
                duplicate, created = submit_video(db, self.character_id, payload, provider)
                self.assertFalse(created)
                self.assertEqual(duplicate.id, first.id)
                with self.assertRaises(HTTPException) as raised:
                    submit_video(db, self.character_id, self.request(), provider)
                self.assertEqual(raised.exception.status_code, 429)
                self.assertEqual(db.get(BetaUsage, "video").used, 1)

    def test_photo_animation_preserves_single_prompt_and_aspect_ratio(self):
        provider = self.provider()
        payload = self.request(aspect_ratio="16:9",
                               prompt='Персонаж машет рукой, рядом шумит дождь. Затем говорит: "Привет!"')
        with self.sessions() as db:
            job, _ = submit_video(db, self.character_id, payload, provider)
            self.assertEqual(job.aspect_ratio, "16:9")
            self.assertEqual(job.prompt, payload.prompt)
            self.assertEqual(job.provider_prompt, 'The character acts and says: "Привет!"')
            with self.assertRaises(HTTPException):
                submit_video(db, self.character_id, payload.model_copy(update={"aspect_ratio": "3:4"}), provider)
        run_video(str(payload.request_id), self.sessions, provider)
        queued_payload = provider.queue.call_args.args[0]
        self.assertEqual(queued_payload["aspect_ratio"], "16:9")
        image_data = base64.b64decode(queued_payload["reference_image_urls"][0].split(",", 1)[1])
        with Image.open(BytesIO(image_data)) as frame:
            self.assertAlmostEqual(frame.width / frame.height, 2 / 3, delta=0.01)
        self.assertEqual(queued_payload["prompt"], 'The character acts and says: "Привет!"')

    def test_reference_video_keeps_speech_at_end_and_sets_portrait_ratio(self):
        provider = self.provider()
        provider.queue.return_value = QueuedVideo("wan-3-0-reference-to-video", "venice-queue-3")
        payload = self.request("reference_video", aspect_ratio="3:4",
                               prompt='Персонаж идёт по парку. Затем говорит: "Привет!"')
        with self.sessions() as db:
            job, _ = submit_video(db, self.character_id, payload, provider)
            self.assertEqual(job.prompt, payload.prompt)
            self.assertTrue(job.provider_prompt.startswith("The two reference images show the same character:"))
            self.assertTrue(job.provider_prompt.endswith('The character acts and says: "Привет!"'))
        run_video(str(payload.request_id), self.sessions, provider)
        queued_payload = provider.queue.call_args.args[0]
        self.assertEqual(queued_payload["prompt"], job.provider_prompt)
        self.assertEqual(queued_payload["aspect_ratio"], "3:4")
        self.assertIs(queued_payload["audio"], True)
        self.assertEqual(queued_payload["resolution"], "480p")

    def test_reference_video_uses_published_face_and_body(self):
        provider = self.provider()
        provider.queue.return_value = QueuedVideo("wan-3-0-reference-to-video", "venice-queue-2")
        payload = self.request("reference_video")
        with self.sessions() as db:
            job, _ = submit_video(db, self.character_id, payload, provider)
            self.assertEqual(job.reference_urls, [self.face, self.body])
            self.assertIn("Image 1 shows the face", job.provider_prompt)
            self.assertIn("Image 2 shows the body", job.provider_prompt)
        run_video(str(payload.request_id), self.sessions, provider)
        self.assertEqual(len(provider.queue.call_args.args[0]["reference_image_urls"]), 2)
        self.assertEqual(provider.queue.call_args.args[0]["aspect_ratio"], "adaptive")

    def test_existing_wan_2_7_job_keeps_its_original_queue_parameters(self):
        provider = self.provider()
        provider.queue.return_value = QueuedVideo("wan-2-7-reference-to-video", "venice-old-queue")
        payload = self.request("reference_video", aspect_ratio="3:4")
        with self.sessions() as db:
            job, _ = submit_video(db, self.character_id, payload, provider)
            job.model = "wan-2-7-reference-to-video"
            job.resolution = "720p"
            db.commit()
        run_video(str(payload.request_id), self.sessions, provider)
        queued_payload = provider.queue.call_args.args[0]
        self.assertEqual(queued_payload["model"], "wan-2-7-reference-to-video")
        self.assertNotIn("aspect_ratio", queued_payload)
        self.assertNotIn("audio", queued_payload)

    def test_existing_wan_2_7_photo_animation_keeps_first_frame_route(self):
        provider = self.provider()
        provider.queue.return_value = QueuedVideo("wan-2-7-enhanced-image-to-video", "venice-old-animation")
        payload = self.request(aspect_ratio="16:9")
        with self.sessions() as db:
            job, _ = submit_video(db, self.character_id, payload, provider)
            job.model = "wan-2-7-enhanced-image-to-video"
            job.resolution = "720p"
            db.commit()
        run_video(str(payload.request_id), self.sessions, provider)
        queued_payload = provider.queue.call_args.args[0]
        self.assertTrue(queued_payload["image_url"].startswith("data:image/jpeg;base64,"))
        self.assertNotIn("reference_image_urls", queued_payload)
        self.assertNotIn("aspect_ratio", queued_payload)
        image_data = base64.b64decode(queued_payload["image_url"].split(",", 1)[1])
        with Image.open(BytesIO(image_data)) as frame:
            self.assertAlmostEqual(frame.width / frame.height, 16 / 9, delta=0.01)

    def test_unsupported_video_settings_rejected_before_paid_request(self):
        provider = self.provider()
        for mode in ("reference_video", "animate_photo"):
            with self.subTest(mode=mode), self.assertRaises(HTTPException) as ratio_error:
                quote_video(VideoQuoteRequest(mode=mode, resolution="480p", aspect_ratio="2:3"), provider)
            self.assertEqual(ratio_error.exception.status_code, 422)
        provider.quote.assert_not_called()

    def test_price_change_and_foreign_photo_are_rejected_before_queue(self):
        provider = self.provider()
        with self.sessions() as db:
            with self.assertRaises(HTTPException) as price_error:
                submit_video(db, self.character_id, self.request(accepted_quote_usd="0.01"), provider)
            self.assertEqual(price_error.exception.status_code, 409)
            with self.assertRaises(HTTPException) as source_error:
                submit_video(db, self.character_id, self.request(source_message_id="missing"), provider)
            self.assertEqual(source_error.exception.status_code, 409)
            self.assertIsNone(db.query(VideoJob).first())

    def test_translation_failure_does_not_reserve_or_queue_video(self):
        provider = self.provider()
        self.translator.translate.side_effect = VideoPromptError("translator unavailable")
        with self.sessions() as db:
            with self.assertRaises(HTTPException) as raised:
                submit_video(db, self.character_id, self.request(), provider)
            self.assertEqual(raised.exception.status_code, 503)
            self.assertIsNone(db.query(VideoJob).first())
            self.assertIsNone(db.get(BetaUsage, "video"))
        provider.queue.assert_not_called()

    def test_unclosed_speech_quotes_are_rejected_before_quote(self):
        provider = self.provider()
        with self.sessions() as db:
            with self.assertRaises(HTTPException) as raised:
                submit_video(db, self.character_id, self.request(prompt='Он говорит: "Привет!'), provider)
            self.assertEqual(raised.exception.status_code, 422)
            self.assertIsNone(db.get(BetaUsage, "video"))
        provider.quote.assert_not_called()

    def test_unknown_queue_outcome_is_not_retried(self):
        provider = self.provider()
        provider.queue.side_effect = VeniceVideoError("connection lost", unknown_outcome=True)
        payload = self.request()
        with self.sessions() as db:
            submit_video(db, self.character_id, payload, provider)
        run_video(str(payload.request_id), self.sessions, provider)
        run_video(str(payload.request_id), self.sessions, provider)
        provider.queue.assert_called_once()
        with self.sessions() as db:
            job = db.get(VideoJob, str(payload.request_id))
            self.assertEqual(job.status, "unknown")
            self.assertEqual(db.get(Message, job.assistant_message_id).video_job_id, "")

    def test_restart_does_not_send_queued_job(self):
        provider = self.provider()
        payload = self.request()
        with self.sessions() as db:
            submit_video(db, self.character_id, payload, provider)
            self.assertEqual(recover_interrupted_videos(db), [])
            self.assertEqual(db.get(VideoJob, str(payload.request_id)).status, "not_started")
        run_video(str(payload.request_id), self.sessions, provider)
        provider.queue.assert_not_called()

    def test_restart_resumes_retrieval_using_existing_queue_id(self):
        provider = self.provider()
        payload = self.request()
        with self.sessions() as db:
            job, _ = submit_video(db, self.character_id, payload, provider)
            job.status = "processing"
            job.queue_id = "venice-existing"
            db.commit()
            self.assertEqual(recover_interrupted_videos(db), [job.id])
        provider.queue.assert_not_called()

    def test_provider_reads_processing_json_and_mp4_stream(self):
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(200, json={"status": "PROCESSING"})
            return httpx.Response(200, content=b"\x00\x00\x00\x18ftypisom00000000",
                                  headers={"content-type": "video/mp4"})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)
        with patch("app.providers.video_venice.httpx.stream", side_effect=client.stream):
            provider = VeniceVideoProvider.__new__(VeniceVideoProvider)
            provider.headers = {"Authorization": "Bearer test"}
            queued = QueuedVideo("wan-2-7-enhanced-image-to-video", "queue-1")
            self.assertEqual(provider.retrieve(queued), ("processing", None))
            status, video = provider.retrieve(queued)
            self.assertEqual(status, "completed")
            self.assertIn(b"ftyp", video)


if __name__ == "__main__":
    unittest.main()
