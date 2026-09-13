import unittest
from base64 import b64encode
import json
from datetime import datetime, timezone
from unittest.mock import patch

import httpx

from app.providers.llm_factory import get_llm_provider
from app.providers import llm_factory
from app.providers.llm_mock_provider import MockLLMProvider
from app.providers.llm_openai_compatible import (
    LLMConfigurationError,
    LLMProviderError,
    OpenAICompatibleLLMProvider,
)
from app.providers import stt_factory
from app.providers.stt_factory import get_stt_provider
from app.providers.stt_openrouter import (
    OpenRouterSTTProvider,
    STTConfigurationError,
    STTProviderError,
)
from app.providers import tts_factory
from app.providers.tts_factory import get_tts_provider
from app.providers.tts_openrouter import (
    OpenRouterTTSProvider,
    TTSConfigurationError,
    TTSProviderError,
)
from app.schemas.llm import character_reply_json_schema
from app.schemas.orchestrator import (
    OrchestratorContext,
    OrchestratorLanguageContext,
    OrchestratorMemoryItem,
    OrchestratorMessageContext,
    OrchestratorProfileContext,
    OrchestratorRoleplayContext,
    OrchestratorSceneContext,
    OrchestratorStateContext,
    OrchestratorUserContext,
    OrchestratorWorldStateContext,
)


def make_context() -> OrchestratorContext:
    now = datetime.now(timezone.utc)
    return OrchestratorContext(
        character_id="character-1",
        character_name="Alice",
        character_gender="female",
        relationship_mode="friend",
        profile=OrchestratorProfileContext(
            personality_description="Warm and thoughtful",
            communication_style="Gentle",
            biography="Test biography",
            boundaries="Respect boundaries",
            likes="Tea",
            dislikes="Noise",
            language="ru",
            user_nickname="Tester",
            warmth=80,
            initiative=65,
            playfulness=40,
            directness=55,
            emotionality=70,
            rationality=60,
        ),
        state=OrchestratorStateContext(mood="curious", trust=20, attachment=10, energy=70),
        user_context=OrchestratorUserContext(
            display_name="Tester",
            formal_name="Test Person",
            preferred_name="Tester",
            casual_name="Test",
            vocative_name="Tester",
            age=30,
            default_name="Tester",
            direct_address_name="Tester",
            address_policy="preferred_by_relationship",
            name_usage_allowed=True,
            name_usage_reason="available_but_optional",
            city="Moscow",
            country="Russia",
            timezone="Europe/Moscow",
            language="ru",
            local_datetime=now,
            local_datetime_iso=now.isoformat(timespec="minutes"),
            local_date=now.date().isoformat(),
            local_time=now.strftime("%H:%M"),
            weekday="Monday",
            time_of_day="daytime",
            daylight_context="daylight is generally plausible",
        ),
        scene_context=OrchestratorSceneContext(
            presence_mode="remote_chat",
            location_name="Private chat",
            location_description="Remote chat from separate places",
            time_description="",
            user_position="at home",
            character_position="at home",
            context_started_at=None,
            can_use_physical_touch=False,
            can_share_immediate_physical_space=False,
        ),
        world_state=OrchestratorWorldStateContext(
            reality_summary="Remote chat. The user and character are not in the same physical space.",
            location_type="remote_chat",
            posture_summary="separate_places",
            physical_touch_policy="impossible in real space; only imagined or roleplayed touch is possible",
            shared_space_policy="no shared immediate physical space",
            movement_policy="do not move into the user's room or walk together",
            allowed_interaction_modes=["text chat", "emotional response"],
        ),
        language_context=OrchestratorLanguageContext(
            slang_terms={},
            smileys={},
            typo_hints={},
            has_colloquial_language=False,
            guidance="Interpret colloquial phrasing generously.",
        ),
        roleplay_context=OrchestratorRoleplayContext(
            action_segments=[],
            thought_segments=[],
            scene_notes=[],
            ooc_notes=[],
            has_roleplay_notation=False,
            response_mode="plain_chat",
        ),
        memory={
            "user_fact": [OrchestratorMemoryItem(id="m1", content="born in December", importance=2, created_at=now)],
            "preference": [],
            "life_event": [],
            "relationship_note": [],
            "system_note": [],
        },
        recent_messages=[
            OrchestratorMessageContext(role="user", content="hello", message_type="text", created_at=now),
            OrchestratorMessageContext(role="assistant", content="hi", message_type="text", created_at=now),
        ],
        current_user_message="How are you?",
    )


class OpenAICompatibleProviderTestCase(unittest.TestCase):
    def test_voice_reply_schema_disallows_private_thought_segments(self) -> None:
        text_kinds = character_reply_json_schema(False)["properties"]["segments"]["items"][
            "properties"
        ]["kind"]["enum"]
        voice_kinds = character_reply_json_schema(True)["properties"]["segments"]["items"][
            "properties"
        ]["kind"]["enum"]

        self.assertIn("thought", text_kinds)
        self.assertNotIn("thought", voice_kinds)

    def test_provider_factory_returns_mock_by_default(self) -> None:
        original_provider = llm_factory.settings.llm_provider
        llm_factory.settings.llm_provider = "mock"
        try:
            provider = get_llm_provider()
        finally:
            llm_factory.settings.llm_provider = original_provider

        self.assertIsInstance(provider, MockLLMProvider)

    def test_provider_factory_returns_openai_compatible_when_configured(self) -> None:
        original_values = (
            llm_factory.settings.llm_provider,
            llm_factory.settings.llm_base_url,
            llm_factory.settings.llm_model,
        )
        llm_factory.settings.llm_provider = "openai_compatible"
        llm_factory.settings.llm_base_url = "http://localhost:11434/v1"
        llm_factory.settings.llm_model = "test-model"
        try:
            provider = get_llm_provider()
        finally:
            (
                llm_factory.settings.llm_provider,
                llm_factory.settings.llm_base_url,
                llm_factory.settings.llm_model,
            ) = original_values

        self.assertIsInstance(provider, OpenAICompatibleLLMProvider)

    def test_provider_sends_expected_request_shape_and_parses_response(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["headers"] = request.headers
            captured["payload"] = request.read()
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "segments": [
                                            {
                                                "kind": "speech",
                                                "text": "Real provider reply",
                                                "audio_cue": "none",
                                            }
                                        ],
                                        "delivery": {
                                            "emotion": "neutral",
                                            "pace": "natural",
                                            "intensity": "balanced",
                                        },
                                    }
                                )
                            }
                        }
                    ]
                },
            )

        provider = OpenAICompatibleLLMProvider(
            base_url="http://localhost:11434/v1",
            api_key="test-key",
            model="test-model",
            timeout_seconds=12,
            temperature=0.7,
            max_tokens=321,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

        reply = provider.generate_reply(make_context())
        payload = json.loads(captured["payload"])

        self.assertEqual(reply.segments[0].text, "Real provider reply")
        self.assertEqual(captured["url"], "http://localhost:11434/v1/chat/completions")
        self.assertEqual(captured["headers"]["authorization"], "Bearer test-key")
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["temperature"], 0.7)
        self.assertEqual(payload["max_tokens"], 321)
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("character_name: Alice", payload["messages"][0]["content"])
        self.assertEqual(payload["messages"][-1], {"role": "user", "content": "How are you?"})

    def test_missing_config_raises_clear_configuration_error(self) -> None:
        provider = OpenAICompatibleLLMProvider(base_url="", api_key="", model="")

        with self.assertRaisesRegex(LLMConfigurationError, "LLM_BASE_URL"):
            provider.generate_reply(make_context())

        provider = OpenAICompatibleLLMProvider(base_url="http://localhost:11434/v1", api_key="", model="")
        with self.assertRaisesRegex(LLMConfigurationError, "LLM_MODEL"):
            provider.generate_reply(make_context())

    def test_non_200_response_raises_clear_provider_error(self) -> None:
        provider = OpenAICompatibleLLMProvider(
            base_url="http://localhost:11434/v1",
            api_key="",
            model="test-model",
            client=httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(500, json={"error": "bad"}))),
        )

        with self.assertRaisesRegex(LLMProviderError, "HTTP 500"):
            provider.generate_reply(make_context())

    def test_malformed_response_raises_clear_provider_error(self) -> None:
        provider = OpenAICompatibleLLMProvider(
            base_url="http://localhost:11434/v1",
            api_key="",
            model="test-model",
            client=httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"choices": []}))),
        )

        with self.assertRaisesRegex(LLMProviderError, "malformed response"):
            provider.generate_reply(make_context())

    def test_invalid_structured_reply_raises_clear_provider_error(self) -> None:
        provider = OpenAICompatibleLLMProvider(
            base_url="http://localhost:11434/v1",
            api_key="",
            model="test-model",
            client=httpx.Client(
                transport=httpx.MockTransport(
                    lambda _request: httpx.Response(
                        200,
                        json={"choices": [{"message": {"content": "not json"}}]},
                    )
                )
            ),
        )

        with self.assertRaisesRegex(LLMProviderError, "malformed structured reply"):
            provider.generate_reply(make_context())

    def test_timeout_raises_clear_provider_error(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timeout")

        provider = OpenAICompatibleLLMProvider(
            base_url="http://localhost:11434/v1",
            api_key="",
            model="test-model",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

        with self.assertRaisesRegex(LLMProviderError, "timed out"):
            provider.generate_reply(make_context())


class OpenRouterSTTProviderTestCase(unittest.TestCase):
    def test_stt_factory_reuses_llm_openrouter_credentials(self) -> None:
        original_values = (
            stt_factory.settings.stt_provider,
            stt_factory.settings.stt_base_url,
            stt_factory.settings.stt_api_key,
            stt_factory.settings.stt_model,
            stt_factory.settings.llm_base_url,
            stt_factory.settings.llm_api_key,
        )
        stt_factory.settings.stt_provider = "openrouter"
        stt_factory.settings.stt_base_url = ""
        stt_factory.settings.stt_api_key = ""
        stt_factory.settings.stt_model = "openai/whisper-large-v3"
        stt_factory.settings.llm_base_url = "https://openrouter.ai/api/v1"
        stt_factory.settings.llm_api_key = "shared-key"
        try:
            provider = get_stt_provider()
        finally:
            (
                stt_factory.settings.stt_provider,
                stt_factory.settings.stt_base_url,
                stt_factory.settings.stt_api_key,
                stt_factory.settings.stt_model,
                stt_factory.settings.llm_base_url,
                stt_factory.settings.llm_api_key,
            ) = original_values

        self.assertIsInstance(provider, OpenRouterSTTProvider)
        self.assertEqual(provider.base_url, "https://openrouter.ai/api/v1")
        self.assertEqual(provider.api_key, "shared-key")
        self.assertEqual(provider.model, "openai/whisper-large-v3")

    def test_stt_provider_sends_audio_without_prompt_and_returns_transcript(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["headers"] = request.headers
            captured["payload"] = request.read()
            return httpx.Response(200, json={"text": "  Проверка распознавания  "})

        provider = OpenRouterSTTProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="openai/whisper-large-v3",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

        transcript = provider.transcribe(b"webm-audio", "audio/webm")
        payload = json.loads(captured["payload"])

        self.assertEqual(transcript, "Проверка распознавания")
        self.assertEqual(captured["url"], "https://openrouter.ai/api/v1/audio/transcriptions")
        self.assertEqual(captured["headers"]["authorization"], "Bearer test-key")
        self.assertEqual(
            payload,
            {
                "model": "openai/whisper-large-v3",
                "input_audio": {
                    "data": b64encode(b"webm-audio").decode("ascii"),
                    "format": "webm",
                },
            },
        )

    def test_stt_provider_reports_configuration_and_remote_errors(self) -> None:
        provider = OpenRouterSTTProvider(base_url="", api_key="", model="")
        with self.assertRaisesRegex(STTConfigurationError, "STT_BASE_URL"):
            provider.transcribe(b"audio", "audio/webm")

        failing_provider = OpenRouterSTTProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="openai/whisper-large-v3",
            client=httpx.Client(
                transport=httpx.MockTransport(
                    lambda _request: httpx.Response(429, json={"error": "busy"})
                )
            ),
        )
        with self.assertRaisesRegex(STTProviderError, "HTTP 429"):
            failing_provider.transcribe(b"audio", "audio/webm")


class OpenRouterTTSProviderTestCase(unittest.TestCase):
    def test_tts_factory_reuses_llm_openrouter_credentials(self) -> None:
        original_values = (
            tts_factory.settings.tts_provider,
            tts_factory.settings.tts_base_url,
            tts_factory.settings.tts_api_key,
            tts_factory.settings.tts_model,
            tts_factory.settings.llm_base_url,
            tts_factory.settings.llm_api_key,
        )
        tts_factory.settings.tts_provider = "openrouter"
        tts_factory.settings.tts_base_url = ""
        tts_factory.settings.tts_api_key = ""
        tts_factory.settings.tts_model = "google/gemini-3.1-flash-tts-preview"
        tts_factory.settings.llm_base_url = "https://openrouter.ai/api/v1"
        tts_factory.settings.llm_api_key = "shared-key"
        try:
            provider = get_tts_provider()
        finally:
            (
                tts_factory.settings.tts_provider,
                tts_factory.settings.tts_base_url,
                tts_factory.settings.tts_api_key,
                tts_factory.settings.tts_model,
                tts_factory.settings.llm_base_url,
                tts_factory.settings.llm_api_key,
            ) = original_values

        self.assertIsInstance(provider, OpenRouterTTSProvider)
        self.assertEqual(provider.base_url, "https://openrouter.ai/api/v1")
        self.assertEqual(provider.api_key, "shared-key")

    def test_tts_provider_sends_voice_and_returns_audio(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["headers"] = request.headers
            captured["payload"] = request.read()
            return httpx.Response(200, content=b"\x01\x02\x03\x04", headers={"Content-Type": "audio/pcm"})

        provider = OpenRouterTTSProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="google/gemini-3.1-flash-tts-preview",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

        provider_input = "# DIRECTOR'S NOTES\nSpeak warmly\n\n# TRANSCRIPT\nПривет"
        result = provider.synthesize(provider_input, "Leda")
        payload = json.loads(captured["payload"])

        self.assertEqual(captured["url"], "https://openrouter.ai/api/v1/audio/speech")
        self.assertEqual(captured["headers"]["authorization"], "Bearer test-key")
        self.assertEqual(payload["model"], "google/gemini-3.1-flash-tts-preview")
        self.assertEqual(payload["voice"], "Leda")
        self.assertEqual(payload["response_format"], "pcm")
        self.assertIn("Speak warmly", payload["input"])
        self.assertIn("Привет", payload["input"])
        self.assertTrue(result.audio_bytes.startswith(b"RIFF"))
        self.assertEqual(result.audio_bytes[8:12], b"WAVE")
        self.assertEqual(result.mime_type, "audio/wav")

    def test_tts_provider_reports_configuration_and_remote_errors(self) -> None:
        provider = OpenRouterTTSProvider(base_url="", api_key="", model="")
        with self.assertRaisesRegex(TTSConfigurationError, "TTS_BASE_URL"):
            provider.synthesize("hello", "Leda")

        failing_provider = OpenRouterTTSProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="google/gemini-3.1-flash-tts-preview",
            client=httpx.Client(
                transport=httpx.MockTransport(
                    lambda _request: httpx.Response(429, json={"error": "busy"})
                )
            ),
        )
        with self.assertRaisesRegex(TTSProviderError, "HTTP 429"):
            failing_provider.synthesize("hello", "Leda")

    def test_tts_provider_retries_transient_empty_audio_response(self) -> None:
        attempts = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return httpx.Response(
                    502,
                    json={"error": {"message": "Provider returned an empty audio stream"}},
                )
            return httpx.Response(200, content=b"\x01\x02", headers={"Content-Type": "audio/pcm"})

        provider = OpenRouterTTSProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="google/gemini-3.1-flash-tts-preview",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

        with patch("app.providers.tts_openrouter.time.sleep") as sleep:
            result = provider.synthesize("hello", "Leda")

        self.assertEqual(attempts, 2)
        sleep.assert_called_once_with(2.0)
        self.assertTrue(result.audio_bytes.startswith(b"RIFF"))

    def test_tts_provider_can_recover_on_third_transient_attempt(self) -> None:
        attempts = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                return httpx.Response(
                    502,
                    json={"error": {"message": "Provider returned an empty audio stream"}},
                )
            return httpx.Response(200, content=b"\x01\x02", headers={"Content-Type": "audio/pcm"})

        provider = OpenRouterTTSProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="google/gemini-3.1-flash-tts-preview",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

        with patch("app.providers.tts_openrouter.time.sleep") as sleep:
            result = provider.synthesize("hello", "Leda")

        self.assertEqual(attempts, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2.0, 4.0])
        self.assertTrue(result.audio_bytes.startswith(b"RIFF"))

    def test_tts_provider_can_recover_after_longer_transient_failure(self) -> None:
        attempts = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts < 4:
                return httpx.Response(
                    502,
                    json={"error": {"message": "Provider returned an empty audio stream"}},
                )
            return httpx.Response(200, content=b"\x01\x02", headers={"Content-Type": "audio/pcm"})

        provider = OpenRouterTTSProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="google/gemini-3.1-flash-tts-preview",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

        with patch("app.providers.tts_openrouter.time.sleep") as sleep:
            result = provider.synthesize("hello", "Leda")

        self.assertEqual(attempts, 4)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2.0, 4.0, 8.0])
        self.assertTrue(result.audio_bytes.startswith(b"RIFF"))

    def test_tts_provider_does_not_retry_invalid_400_input(self) -> None:
        inputs: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.read())
            inputs.append(payload["input"])
            return httpx.Response(400, json={"error": {"message": "Provider returned 400"}})

        provider = OpenRouterTTSProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="google/gemini-3.1-flash-tts-preview",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

        with self.assertRaisesRegex(TTSProviderError, "HTTP 400"):
            provider.synthesize("# TRANSCRIPT\nПривет", "Leda")

        self.assertEqual(inputs, ["# TRANSCRIPT\nПривет"])


if __name__ == "__main__":
    unittest.main()
