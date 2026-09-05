from base64 import b64encode
from typing import Any

import httpx


class STTConfigurationError(ValueError):
    pass


class STTProviderError(RuntimeError):
    pass


AUDIO_FORMATS = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}


class OpenRouterSTTProvider:
    name = "openrouter"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 90,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.strip()
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.timeout_seconds = timeout_seconds
        self.client = client

    def transcribe(self, audio_bytes: bytes, mime_type: str) -> str:
        self._validate_config()
        audio_format = AUDIO_FORMATS.get(mime_type.partition(";")[0].strip().lower())
        if not audio_format:
            raise STTProviderError("STT provider does not support this audio format")

        payload = {
            "model": self.model,
            "input_audio": {
                "data": b64encode(audio_bytes).decode("ascii"),
                "format": audio_format,
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = self._post_transcription(payload, headers)
        except httpx.TimeoutException as exc:
            raise STTProviderError("Speech recognition timed out") from exc
        except httpx.HTTPError as exc:
            raise STTProviderError("Speech recognition request failed") from exc

        if response.status_code != 200:
            detail = response.text.strip().replace("\n", " ")[:500]
            message = f"Speech recognition returned HTTP {response.status_code}"
            if detail:
                message = f"{message}: {detail}"
            raise STTProviderError(message)

        try:
            data = response.json()
            text = data["text"]
        except (KeyError, TypeError, ValueError) as exc:
            raise STTProviderError("Speech recognition returned a malformed response") from exc

        if not isinstance(text, str) or not text.strip():
            raise STTProviderError("No speech was recognized in the recording")
        return text.strip()

    def _validate_config(self) -> None:
        if not self.base_url:
            raise STTConfigurationError("STT_BASE_URL or LLM_BASE_URL is required")
        if not self.api_key:
            raise STTConfigurationError("STT_API_KEY or LLM_API_KEY is required")
        if not self.model:
            raise STTConfigurationError("STT_MODEL is required")

    def _post_transcription(self, payload: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
        url = f"{self.base_url.rstrip('/')}/audio/transcriptions"
        if self.client:
            return self.client.post(url, json=payload, headers=headers, timeout=self.timeout_seconds)
        with httpx.Client(timeout=self.timeout_seconds) as client:
            return client.post(url, json=payload, headers=headers)
