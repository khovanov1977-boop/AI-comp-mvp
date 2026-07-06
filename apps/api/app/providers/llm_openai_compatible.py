from typing import Any

import httpx

from app.schemas.orchestrator import OrchestratorContext
from app.services.prompt_builder import ProviderMessage, build_provider_prompt


class LLMConfigurationError(ValueError):
    pass


class LLMProviderError(RuntimeError):
    pass


class OpenAICompatibleLLMProvider:
    name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 60,
        temperature: float = 0.8,
        max_tokens: int = 500,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.strip()
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = client

    def generate_reply(self, context: OrchestratorContext) -> str:
        self._validate_config()
        prompt = build_provider_prompt(context)
        payload = {
            "model": self.model,
            "messages": self._to_openai_messages(prompt.messages, prompt.system),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = self._post_chat_completions(payload, headers)
        except httpx.TimeoutException as exc:
            raise LLMProviderError("LLM provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError("LLM provider request failed") from exc

        if response.status_code != 200:
            raise LLMProviderError(f"LLM provider returned HTTP {response.status_code}")

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMProviderError("LLM provider returned malformed response") from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMProviderError("LLM provider returned empty response")
        return content

    def _validate_config(self) -> None:
        if not self.base_url:
            raise LLMConfigurationError("LLM_BASE_URL is required for openai_compatible provider")
        if not self.model:
            raise LLMConfigurationError("LLM_MODEL is required for openai_compatible provider")

    def _post_chat_completions(self, payload: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        if self.client:
            return self.client.post(url, json=payload, headers=headers, timeout=self.timeout_seconds)
        with httpx.Client(timeout=self.timeout_seconds) as client:
            return client.post(url, json=payload, headers=headers)

    @staticmethod
    def _to_openai_messages(messages: list[ProviderMessage], system_prompt: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system_prompt},
            *[{"role": message.role, "content": message.content} for message in messages],
        ]
