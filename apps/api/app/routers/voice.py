from pydantic import BaseModel
from fastapi import APIRouter

from app.services.voice_service import speech_to_text, text_to_speech

router = APIRouter(prefix="/voice", tags=["voice"])


class TtsRequest(BaseModel):
    text: str


class SttRequest(BaseModel):
    audio_url: str


@router.post("/tts")
def tts(payload: TtsRequest) -> dict[str, str]:
    return {"audio_url": text_to_speech(payload.text)}


@router.post("/stt")
def stt(payload: SttRequest) -> dict[str, str]:
    return {"text": speech_to_text(payload.audio_url)}
