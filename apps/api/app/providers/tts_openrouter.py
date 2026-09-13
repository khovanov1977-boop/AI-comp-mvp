from io import BytesIO
from typing import Any
import time
import wave

import httpx

from app.providers.tts_base import SynthesizedSpeech


class TTSConfigurationError(ValueError):
    pass


class TTSProviderError(RuntimeError):
    pass


RESPONSE_MIME_TYPES = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "pcm": "audio/pcm",
}
TRANSIENT_STATUS_CODES = {500, 502, 503, 504}
MAX_TRANSIENT_ATTEMPTS = 4
TRANSIENT_RETRY_DELAY_SECONDS = 2.0


class OpenRouterTTSProvider:
    name = "openrouter"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 90,
        response_format: str = "pcm",
        pcm_sample_rate_hz: int = 24000,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.strip()
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.timeout_seconds = timeout_seconds
        self.response_format = response_format.strip().lower() or "pcm"
        self.pcm_sample_rate_hz = pcm_sample_rate_hz
        self.client = client

    def synthesize(self, provider_input: str, voice_id: str) -> SynthesizedSpeech:
        self._validate_config()
        provider_input = provider_input.strip()
        if not provider_input:
            raise TTSProviderError("A non-empty TTS input is required for speech generation")

        payload = {
            "model": self.model,
            "input": provider_input,
            "voice": voice_id,
            "response_format": self.response_format,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response: httpx.Response | None = None
        for attempt in range(MAX_TRANSIENT_ATTEMPTS):
            try:
                response = self._post_speech(payload, headers)
            except httpx.TimeoutException as exc:
                raise TTSProviderError("Voice generation timed out") from exc
            except httpx.HTTPError as exc:
                raise TTSProviderError("Voice generation request failed") from exc

            received_audio = response.status_code == 200 and bool(response.content)
            retryable_failure = response.status_code in TRANSIENT_STATUS_CODES or (
                response.status_code == 200 and not response.content
            )
            if received_audio or not retryable_failure or attempt == MAX_TRANSIENT_ATTEMPTS - 1:
                break
            time.sleep(TRANSIENT_RETRY_DELAY_SECONDS * (2**attempt))

        if response is None:
            raise TTSProviderError("Voice generation request failed")

        if response.status_code != 200:
            detail = response.text.strip().replace("\n", " ")[:500]
            message = f"Voice generation returned HTTP {response.status_code}"
            if detail:
                message = f"{message}: {detail}"
            raise TTSProviderError(message)
        if not response.content:
            raise TTSProviderError("Voice generation returned empty audio")

        if self.response_format == "pcm":
            return SynthesizedSpeech(
                audio_bytes=self._wrap_pcm_as_wav(response.content),
                mime_type="audio/wav",
            )

        content_type = response.headers.get("content-type", "").partition(";")[0].strip().lower()
        mime_type = content_type if content_type.startswith("audio/") else RESPONSE_MIME_TYPES[self.response_format]
        return SynthesizedSpeech(audio_bytes=response.content, mime_type=mime_type)

    def _validate_config(self) -> None:
        if not self.base_url:
            raise TTSConfigurationError("TTS_BASE_URL or LLM_BASE_URL is required")
        if not self.api_key:
            raise TTSConfigurationError("TTS_API_KEY or LLM_API_KEY is required")
        if not self.model:
            raise TTSConfigurationError("TTS_MODEL is required")
        if self.response_format not in {"mp3", "pcm"}:
            raise TTSConfigurationError("TTS_RESPONSE_FORMAT must be mp3 or pcm")
        if self.pcm_sample_rate_hz <= 0:
            raise TTSConfigurationError("TTS_PCM_SAMPLE_RATE_HZ must be positive")

    def _wrap_pcm_as_wav(self, pcm_bytes: bytes) -> bytes:
        output = BytesIO()
        with wave.open(output, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.pcm_sample_rate_hz)
            wav_file.writeframes(pcm_bytes)
        return output.getvalue()

    def _post_speech(self, payload: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
        url = f"{self.base_url.rstrip('/')}/audio/speech"
        if self.client:
            return self.client.post(url, json=payload, headers=headers, timeout=self.timeout_seconds)
        with httpx.Client(timeout=self.timeout_seconds) as client:
            return client.post(url, json=payload, headers=headers)
