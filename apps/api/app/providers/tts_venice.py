"""Gemini voice generation through Venice's OpenAI-compatible speech endpoint."""

import httpx

from app.providers.tts_openrouter import OpenRouterTTSProvider, TTSConfigurationError


class VeniceTTSProvider(OpenRouterTTSProvider):
    name = "venice"

    def __init__(
        self,
        api_key: str,
        model: str = "tts-gemini-3-1-flash",
        timeout_seconds: int = 180,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            base_url="https://api.venice.ai/api/v1",
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            response_format="mp3",
            client=client,
        )

    def _validate_config(self) -> None:
        if not self.api_key or not self.model:
            raise TTSConfigurationError("Voice generation is not configured")
