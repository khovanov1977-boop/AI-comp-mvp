from app.config import settings
from app.providers.llm_base import LLMProvider
from app.providers.llm_mock_provider import MockLLMProvider
from app.providers.llm_openai_compatible import OpenAICompatibleLLMProvider
from app.providers.llm_venice import VeniceLLMProvider


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    selected_provider = (provider_name or settings.llm_provider).strip().lower()
    if selected_provider == "mock":
        return MockLLMProvider()
    if selected_provider == "openai_compatible":
        return OpenAICompatibleLLMProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            fallback_models=tuple(model.strip() for model in settings.llm_fallback_models.split(",") if model.strip()),
            timeout_seconds=settings.llm_timeout_seconds,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
    if selected_provider == "venice":
        return VeniceLLMProvider(
            api_key=settings.venice_api_key,
            model=settings.venice_llm_model,
            fallback_models=settings.effective_llm_fallback_models,
            timeout_seconds=settings.llm_timeout_seconds,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
    raise ValueError(f"Unsupported LLM provider: {selected_provider}")
