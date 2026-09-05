from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.character import Character
from app.models.message import Message
from app.providers.llm_openai_compatible import LLMConfigurationError, LLMProviderError
from app.providers.stt_openrouter import STTConfigurationError, STTProviderError
from app.schemas.chat import CharacterStateRead, VoiceChatResponse
from app.services.orchestrator import handle_existing_user_message
from app.services.voice_service import speech_to_text, text_to_speech
from app.services.voice_storage import (
    MAX_VOICE_DURATION_MS,
    VoiceFileTooLargeError,
    VoiceStorageError,
    delete_voice_file,
    read_voice_file,
    save_voice_file,
)

router = APIRouter(prefix="/voice", tags=["voice"])


class TtsRequest(BaseModel):
    text: str


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


def voice_chat_response(
    message: Message,
    character: Character,
    reply: str | None = None,
    error_type: str = "",
    error_message: str = "",
) -> VoiceChatResponse:
    return VoiceChatResponse(
        message=message,
        reply=reply,
        character_state=CharacterStateRead(
            mood=character.state.mood,
            trust_level=character.state.trust_level,
            attachment_level=character.state.attachment_level,
            energy_level=character.state.energy_level,
        ),
        error_type=error_type,
        error_message=error_message,
    )


def process_voice_message(db: Session, character: Character, message: Message) -> VoiceChatResponse:
    message.transcription_status = "pending"
    message.transcription_error = ""
    db.add(message)
    db.commit()

    try:
        transcript = speech_to_text(read_voice_file(message.audio_url), message.audio_mime_type)
    except (STTConfigurationError, STTProviderError, VoiceStorageError) as exc:
        message.transcription_status = "failed"
        message.transcription_error = str(exc)
        db.add(message)
        db.commit()
        db.refresh(message)
        return voice_chat_response(
            message,
            character,
            error_type="transcription_error",
            error_message=str(exc),
        )

    message.content = transcript
    message.transcription_status = "completed"
    message.transcription_error = ""
    db.add(message)
    db.commit()
    db.refresh(message)

    try:
        reply, _assistant_message = handle_existing_user_message(db, character, message)
    except LLMConfigurationError as exc:
        db.rollback()
        return voice_chat_response(
            message,
            character,
            error_type="llm_configuration_error",
            error_message=str(exc),
        )
    except LLMProviderError as exc:
        db.rollback()
        return voice_chat_response(
            message,
            character,
            error_type="llm_provider_error",
            error_message=str(exc),
        )
    except Exception as exc:
        db.rollback()
        return voice_chat_response(
            message,
            character,
            error_type="chat_error",
            error_message=str(exc) or exc.__class__.__name__,
        )

    db.refresh(message)
    return voice_chat_response(message, character, reply=reply)


@router.post("/messages/{character_id}", response_model=VoiceChatResponse)
async def create_voice_message(
    character_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> VoiceChatResponse:
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
        transcription_status="pending",
    )
    try:
        db.add(message)
        db.commit()
        db.refresh(message)
    except Exception:
        db.rollback()
        delete_voice_file(audio_url)
        raise
    return process_voice_message(db, character, message)


@router.post("/messages/{message_id}/retry", response_model=VoiceChatResponse)
def retry_voice_transcription(message_id: str, db: Session = Depends(get_db)) -> VoiceChatResponse:
    message = db.get(Message, message_id)
    if not message or message.message_type != "voice" or message.role != "user":
        raise HTTPException(status_code=404, detail="Voice message not found")
    if message.transcription_status not in {"pending", "failed"}:
        raise HTTPException(status_code=400, detail="Voice message is not waiting for transcription retry")

    character = db.get(Character, message.character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return process_voice_message(db, character, message)


@router.post("/tts")
def tts(payload: TtsRequest) -> dict[str, str]:
    return {"audio_url": text_to_speech(payload.text)}
