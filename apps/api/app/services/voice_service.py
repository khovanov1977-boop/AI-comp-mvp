from app.providers.tts_mock import synthesize_speech
from app.providers.stt_factory import get_stt_provider


def text_to_speech(text: str) -> str:
    return synthesize_speech(text)


def speech_to_text(audio_bytes: bytes, mime_type: str) -> str:
    return get_stt_provider().transcribe(audio_bytes, mime_type)
