"""Venice chat provider with ordered model failover."""

import logging

from app.providers.llm_openai_compatible import (
    LLMConfigurationError,
    LLMProviderError,
    OpenAICompatibleLLMProvider,
)
from app.schemas.llm import CharacterReply
from app.schemas.orchestrator import OrchestratorContext


logger = logging.getLogger(__name__)


class VeniceLLMProvider:
    name = "venice"

    def __init__(
        self,
        api_key: str,
        model: str,
        fallback_models: tuple[str, ...] = (),
        timeout_seconds: int = 60,
        temperature: float = 0.3,
        max_tokens: int = 500,
    ) -> None:
        self.api_key = api_key.strip()
        self.models = tuple(dict.fromkeys(item.strip() for item in (model, *fallback_models) if item.strip()))
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate_reply(self, context: OrchestratorContext) -> CharacterReply:
        if not self.api_key or not self.models:
            raise LLMConfigurationError("Chat service is not configured")
        last_error: LLMProviderError | None = None
        for model in self.models:
            provider = OpenAICompatibleLLMProvider(
                base_url="https://api.venice.ai/api/v1",
                api_key=self.api_key,
                model=model,
                timeout_seconds=self.timeout_seconds,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            try:
                return provider.generate_reply(context)
            except LLMProviderError as exc:
                logger.warning("venice_llm_model_failed model=%s reason=%s", model, str(exc))
                last_error = exc
        raise LLMProviderError("Chat service is temporarily unavailable") from last_error
