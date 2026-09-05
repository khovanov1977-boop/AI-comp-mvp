from typing import Protocol


class STTProvider(Protocol):
    name: str

    def transcribe(self, audio_bytes: bytes, mime_type: str) -> str:
        ...
