from app.config import settings
from app.providers.llm_base import LLMProvider
from app.providers.llm_mock_provider import MockLLMProvider
from app.providers.llm_openai_compatible import OpenAICompatibleLLMProvider


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    selected_provider = (provider_name or settings.llm_provider).strip().lower()
    if selected_provider == "mock":
        return MockLLMProvider()
    if selected_provider == "openai_compatible":
        return OpenAICompatibleLLMProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
    raise ValueError(f"Unsupported LLM provider: {selected_provider}")
