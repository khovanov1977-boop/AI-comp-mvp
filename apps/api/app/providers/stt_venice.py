"""Speech recognition through Venice's multipart transcription endpoint."""

import httpx

from app.providers.stt_openrouter import AUDIO_FORMATS, STTConfigurationError, STTProviderError


class VeniceSTTProvider:
    name = "venice"

    def __init__(
        self,
        api_key: str,
        model: str = "openai/whisper-large-v3",
        timeout_seconds: int = 90,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = "https://api.venice.ai/api/v1"
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.timeout_seconds = timeout_seconds
        self.client = client

    def transcribe(self, audio_bytes: bytes, mime_type: str) -> str:
        if not self.api_key or not self.model:
            raise STTConfigurationError("Speech recognition is not configured")
        normalized_mime = mime_type.partition(";")[0].strip().lower()
        extension = AUDIO_FORMATS.get(normalized_mime)
        if not extension:
            raise STTProviderError("Speech recognition does not support this audio format")
        if not audio_bytes:
            raise STTProviderError("The recording is empty")

        url = f"{self.base_url}/audio/transcriptions"
        files = {"file": (f"recording.{extension}", audio_bytes, normalized_mime)}
        data = {"model": self.model, "response_format": "json", "timestamps": "false"}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            if self.client:
                response = self.client.post(url, data=data, files=files, headers=headers,
                                            timeout=self.timeout_seconds)
            else:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(url, data=data, files=files, headers=headers)
        except httpx.TimeoutException as exc:
            raise STTProviderError("Speech recognition timed out") from exc
        except httpx.HTTPError as exc:
            raise STTProviderError("Speech recognition request failed") from exc

        if response.status_code != 200:
            raise STTProviderError(f"Speech recognition returned HTTP {response.status_code}")
        try:
            text = response.json()["text"]
        except (KeyError, TypeError, ValueError) as exc:
            raise STTProviderError("Speech recognition returned a malformed response") from exc
        if not isinstance(text, str) or not text.strip():
            raise STTProviderError("No speech was recognized in the recording")
        return text.strip()
