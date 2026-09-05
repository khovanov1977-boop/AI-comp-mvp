from app.config import settings
from app.providers.stt_base import STTProvider
from app.providers.stt_openrouter import OpenRouterSTTProvider, STTConfigurationError


def get_stt_provider(provider_name: str | None = None) -> STTProvider:
    selected_provider = (provider_name or settings.stt_provider).strip().lower()
    if selected_provider == "openrouter":
        return OpenRouterSTTProvider(
            base_url=settings.stt_base_url or settings.llm_base_url,
            api_key=settings.stt_api_key or settings.llm_api_key,
            model=settings.stt_model,
            timeout_seconds=settings.stt_timeout_seconds,
        )
    raise STTConfigurationError(f"Unsupported STT provider: {selected_provider}")
