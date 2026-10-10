import json
import unittest
from unittest.mock import patch

import httpx

from app.config import Settings
from app.providers.stt_factory import get_stt_provider
from app.providers.stt_openrouter import STTProviderError
from app.providers.stt_venice import VeniceSTTProvider
from app.providers.tts_factory import get_tts_provider
from app.providers.tts_openrouter import TTSConfigurationError
from app.providers.tts_venice import VeniceTTSProvider


class VeniceAudioTest(unittest.TestCase):
    def test_factories_use_venice_key_and_models(self):
        config = Settings(
            _env_file=None,
            stt_provider="venice",
            tts_provider="venice",
            venice_api_key="test-venice-key",
            llm_api_key="different-legacy-key",
        )
        with patch("app.providers.stt_factory.settings", config), patch("app.providers.tts_factory.settings", config):
            stt = get_stt_provider()
            tts = get_tts_provider()
        self.assertIsInstance(stt, VeniceSTTProvider)
        self.assertEqual(stt.api_key, "test-venice-key")
        self.assertEqual(stt.model, "openai/whisper-large-v3")
        self.assertIsInstance(tts, VeniceTTSProvider)
        self.assertEqual(tts.api_key, "test-venice-key")
        self.assertEqual(tts.model, "tts-gemini-3-1-flash")
        self.assertEqual(tts.response_format, "mp3")

    def test_transcription_uploads_audio_file_as_multipart(self):
        def handler(request):
            self.assertEqual(str(request.url), "https://api.venice.ai/api/v1/audio/transcriptions")
            self.assertEqual(request.headers["authorization"], "Bearer test-key")
            self.assertIn("multipart/form-data", request.headers["content-type"])
            body = request.read()
            self.assertIn(b'filename="recording.webm"', body)
            self.assertIn(b"openai/whisper-large-v3", body)
            self.assertIn(b"audio-test-bytes", body)
            self.assertIn(b"response_format", body)
            return httpx.Response(200, json={"text": "  Привет, как дела?  "})

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            provider = VeniceSTTProvider("test-key", client=client)
            result = provider.transcribe(b"audio-test-bytes", "audio/webm;codecs=opus")
        self.assertEqual(result, "Привет, как дела?")

    def test_transcription_rejects_empty_audio_and_bad_response(self):
        provider = VeniceSTTProvider("test-key")
        with self.assertRaisesRegex(STTProviderError, "empty"):
            provider.transcribe(b"", "audio/webm")
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"text": ""}))) as client:
            with self.assertRaisesRegex(STTProviderError, "No speech"):
                VeniceSTTProvider("test-key", client=client).transcribe(b"data", "audio/webm")

    def test_speech_uses_existing_voice_id_and_mp3(self):
        def handler(request):
            self.assertEqual(str(request.url), "https://api.venice.ai/api/v1/audio/speech")
            self.assertEqual(request.headers["authorization"], "Bearer test-key")
            payload = json.loads(request.read())
            self.assertEqual(payload["model"], "tts-gemini-3-1-flash")
            self.assertEqual(payload["voice"], "Leda")
            self.assertEqual(payload["response_format"], "mp3")
            self.assertEqual(payload["input"], "Привет!")
            return httpx.Response(200, content=b"\xff\xfbvalid-mp3", headers={"content-type": "audio/mpeg"})

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            speech = VeniceTTSProvider("test-key", client=client).synthesize("Привет!", "Leda")
        self.assertEqual(speech.mime_type, "audio/mpeg")
        self.assertTrue(speech.audio_bytes.startswith(b"\xff\xfb"))

    def test_speech_requires_venice_key(self):
        with self.assertRaisesRegex(TTSConfigurationError, "not configured"):
            VeniceTTSProvider("").synthesize("Привет!", "Leda")
