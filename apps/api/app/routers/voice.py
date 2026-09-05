from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.character import Character
from app.models.message import Message
from app.schemas.chat import MessageRead
from app.services.voice_service import speech_to_text, text_to_speech
from app.services.voice_storage import (
    MAX_VOICE_DURATION_MS,
    VoiceFileTooLargeError,
    VoiceStorageError,
    delete_voice_file,
    save_voice_file,
)

router = APIRouter(prefix="/voice", tags=["voice"])


class TtsRequest(BaseModel):
    text: str


class SttRequest(BaseModel):
    audio_url: str


def parse_audio_duration(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        duration_ms = int(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid voice message duration") from exc
    if duration_ms <= 0:
        raise HTTPException(status_code=400, detail="Voice message duration must be positive")
    if duration_ms > MAX_VOICE_DURATION_MS:
        raise HTTPException(status_code=400, detail="Voice message is longer than 2 minutes")
    return duration_ms


@router.post("/messages/{character_id}", response_model=MessageRead)
async def create_voice_message(
    character_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> MessageRead:
    character = db.get(Character, character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    duration_ms = parse_audio_duration(request.headers.get("x-audio-duration-ms"))
    audio_bytes = await request.body()
    try:
        audio_url, mime_type = save_voice_file(
            character_id,
            audio_bytes,
            request.headers.get("content-type", ""),
        )
    except VoiceFileTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except VoiceStorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    message = Message(
        character_id=character_id,
        role="user",
        content="",
        message_type="voice",
        audio_url=audio_url,
        audio_mime_type=mime_type,
        audio_duration_ms=duration_ms,
    )
    try:
        db.add(message)
        db.commit()
        db.refresh(message)
    except Exception:
        db.rollback()
        delete_voice_file(audio_url)
        raise
    return message


@router.post("/tts")
def tts(payload: TtsRequest) -> dict[str, str]:
    return {"audio_url": text_to_speech(payload.text)}


@router.post("/stt")
def stt(payload: SttRequest) -> dict[str, str]:
    return {"text": speech_to_text(payload.audio_url)}
