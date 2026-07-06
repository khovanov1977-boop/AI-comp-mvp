import unittest
import json
from datetime import datetime, timezone

import httpx

from app.providers.llm_factory import get_llm_provider
from app.providers import llm_factory
from app.providers.llm_mock_provider import MockLLMProvider
from app.providers.llm_openai_compatible import (
    LLMConfigurationError,
    LLMProviderError,
    OpenAICompatibleLLMProvider,
)
from app.schemas.orchestrator import (
    OrchestratorContext,
    OrchestratorMemoryItem,
    OrchestratorMessageContext,
    OrchestratorProfileContext,
    OrchestratorStateContext,
)


def make_context() -> OrchestratorContext:
    now = datetime.now(timezone.utc)
    return OrchestratorContext(
        character_id="character-1",
        character_name="Alice",
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
        ),
        state=OrchestratorStateContext(mood="curious", trust=20, attachment=10, energy=70),
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
                json={"choices": [{"message": {"content": "Real provider reply"}}]},
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

        self.assertEqual(reply, "Real provider reply")
        self.assertEqual(captured["url"], "http://localhost:11434/v1/chat/completions")
        self.assertEqual(captured["headers"]["authorization"], "Bearer test-key")
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["temperature"], 0.7)
        self.assertEqual(payload["max_tokens"], 321)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("Character: Alice", payload["messages"][0]["content"])
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


if __name__ == "__main__":
    unittest.main()
