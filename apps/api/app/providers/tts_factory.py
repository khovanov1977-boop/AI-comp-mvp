from app.config import settings
from app.providers.tts_base import TTSProvider
from app.providers.tts_openrouter import OpenRouterTTSProvider, TTSConfigurationError


def get_tts_provider(provider_name: str | None = None) -> TTSProvider:
    selected_provider = (provider_name or settings.tts_provider).strip().lower()
    if selected_provider == "openrouter":
        return OpenRouterTTSProvider(
            base_url=settings.tts_base_url or settings.llm_base_url,
            api_key=settings.tts_api_key or settings.llm_api_key,
            model=settings.tts_model,
            timeout_seconds=settings.tts_timeout_seconds,
            response_format=settings.tts_response_format,
            pcm_sample_rate_hz=settings.tts_pcm_sample_rate_hz,
        )
    raise TTSConfigurationError(f"Unsupported TTS provider: {selected_provider}")
