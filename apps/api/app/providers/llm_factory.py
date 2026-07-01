from app.config import settings
from app.providers.llm_base import LLMProvider
from app.providers.llm_mock_provider import MockLLMProvider


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    selected_provider = (provider_name or settings.llm_provider).strip().lower()
    if selected_provider == "mock":
        return MockLLMProvider()
    raise ValueError(f"Unsupported LLM provider: {selected_provider}")
