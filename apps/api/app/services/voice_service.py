from app.providers.stt_mock import transcribe_audio
from app.providers.tts_mock import synthesize_speech


def text_to_speech(text: str) -> str:
    return synthesize_speech(text)


def speech_to_text(url: str) -> str:
    return transcribe_audio(url)
