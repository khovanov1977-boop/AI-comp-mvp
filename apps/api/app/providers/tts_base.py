from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SynthesizedSpeech:
    audio_bytes: bytes
    mime_type: str


class TTSProvider(Protocol):
    name: str

    def synthesize(self, provider_input: str, voice_id: str) -> SynthesizedSpeech:
        ...
