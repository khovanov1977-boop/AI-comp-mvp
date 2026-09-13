from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.character import Character
from app.models.message import Message
from app.providers.llm_openai_compatible import LLMConfigurationError, LLMProviderError
from app.providers.stt_openrouter import STTConfigurationError, STTProviderError
from app.schemas.chat import CharacterStateRead, MessageRead, VoiceChatResponse
from app.schemas.voice import VoiceOptionRead, VoicePreviewRequest, VoiceUploadConstraintsRead
from app.services.orchestrator import handle_existing_user_message
from app.services.voice_catalog import catalog_payload
from app.services.voice_service import (
    attach_prepared_character_voice,
    prepare_character_voice,
    speech_to_text,
    synthesize_voice_preview,
)
from app.services.voice_storage import (
    MAX_VOICE_DURATION_MS,
    MAX_VOICE_BYTES,
    SUPPORTED_AUDIO_TYPES,
    VoiceFileTooLargeError,
    VoiceStorageError,
    delete_voice_file,
    read_voice_file,
    save_voice_file,
)
from app.providers.tts_openrouter import TTSConfigurationError, TTSProviderError

router = APIRouter(prefix="/voice", tags=["voice"])


def parse_audio_duration(value: str | None) -> int:
    if value is None:
        raise HTTPException(status_code=400, detail="Voice message duration is required")
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


def transcribe_voice_message(db: Session, character: Character, message: Message) -> VoiceChatResponse:
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

    return voice_chat_response(message, character)


def generate_voice_response(db: Session, character: Character, message: Message) -> VoiceChatResponse:
    next_message = db.scalar(
        select(Message)
        .where(
            Message.character_id == character.id,
            Message.created_at > message.created_at,
        )
        .order_by(Message.created_at.asc())
        .limit(1)
    )
    if next_message:
        if next_message.role != "assistant":
            raise HTTPException(status_code=409, detail="Voice message is no longer waiting for a reply")
        error_type = "" if next_message.message_type == "voice" else "voice_generation_error"
        error_message = (
            ""
            if next_message.message_type == "voice"
            else "Text reply was already saved, but generated audio is unavailable"
        )
        return voice_chat_response(
            message,
            character,
            reply=next_message.content,
            error_type=error_type,
            error_message=error_message,
        )

    try:
        reply, assistant_message, reply_plan = handle_existing_user_message(db, character, message)
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

    try:
        prepare_character_voice(character, assistant_message, reply_plan)
        db.add(assistant_message)
        db.commit()
        attach_prepared_character_voice(assistant_message)
        db.add(assistant_message)
        db.commit()
    except (TTSConfigurationError, TTSProviderError, VoiceStorageError) as exc:
        db.rollback()
        db.refresh(assistant_message)
        assistant_message.voice_generation_status = "failed"
        assistant_message.voice_generation_error = str(exc)
        db.add(assistant_message)
        db.commit()
        db.refresh(message)
        return voice_chat_response(
            message,
            character,
            reply=reply,
            error_type="voice_generation_error",
            error_message=f"Text reply was saved, but voice generation failed: {exc}",
        )
    except Exception as exc:
        db.rollback()
        db.refresh(assistant_message)
        assistant_message.voice_generation_status = "failed"
        assistant_message.voice_generation_error = str(exc) or exc.__class__.__name__
        db.add(assistant_message)
        db.commit()
        db.refresh(message)
        return voice_chat_response(
            message,
            character,
            reply=reply,
            error_type="voice_generation_error",
            error_message=f"Text reply was saved, but voice generation failed: {str(exc) or exc.__class__.__name__}",
        )

    db.refresh(message)
    return voice_chat_response(message, character, reply=reply)


def process_voice_message(db: Session, character: Character, message: Message) -> VoiceChatResponse:
    transcription = transcribe_voice_message(db, character, message)
    if transcription.error_type:
        return transcription
    return generate_voice_response(db, character, message)


async def store_voice_message(
    character_id: str,
    request: Request,
    db: Session,
) -> Message:
    upload_id = request.headers.get("x-voice-upload-id", "").strip()
    if upload_id:
        try:
            upload_id = str(UUID(upload_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid voice upload ID") from exc
        existing_message = db.get(Message, upload_id)
        if existing_message:
            if (
                existing_message.character_id != character_id
                or existing_message.role != "user"
                or existing_message.message_type != "voice"
            ):
                raise HTTPException(status_code=409, detail="Voice upload ID is already in use")
            return existing_message

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

    message_values = dict(
        character_id=character_id,
        role="user",
        content="",
        message_type="voice",
        audio_url=audio_url,
        audio_mime_type=mime_type,
        audio_duration_ms=duration_ms,
        transcription_status="pending",
    )
    if upload_id:
        message_values["id"] = upload_id
    message = Message(**message_values)
    try:
        db.add(message)
        db.commit()
        db.refresh(message)
    except Exception:
        db.rollback()
        delete_voice_file(audio_url)
        raise
    return message


@router.post("/messages/{character_id}", response_model=VoiceChatResponse)
async def create_voice_message(
    character_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> VoiceChatResponse:
    character = db.get(Character, character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    message = await store_voice_message(character_id, request, db)
    if message.transcription_status == "completed":
        return generate_voice_response(db, character, message)
    return process_voice_message(db, character, message)


@router.post("/messages/{character_id}/upload", response_model=MessageRead)
async def upload_voice_message(
    character_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Message:
    character = db.get(Character, character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return await store_voice_message(character_id, request, db)


@router.post("/messages/{message_id}/transcribe", response_model=VoiceChatResponse)
def transcribe_uploaded_voice(message_id: str, db: Session = Depends(get_db)) -> VoiceChatResponse:
    message = db.get(Message, message_id)
    if not message or message.message_type != "voice" or message.role != "user":
        raise HTTPException(status_code=404, detail="Voice message not found")
    if message.transcription_status not in {"pending", "failed"}:
        raise HTTPException(status_code=400, detail="Voice message is not waiting for transcription")

    character = db.get(Character, message.character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return transcribe_voice_message(db, character, message)


@router.post("/messages/{message_id}/reply", response_model=VoiceChatResponse)
def generate_uploaded_voice_reply(message_id: str, db: Session = Depends(get_db)) -> VoiceChatResponse:
    message = db.get(Message, message_id)
    if not message or message.message_type != "voice" or message.role != "user":
        raise HTTPException(status_code=404, detail="Voice message not found")
    if message.transcription_status != "completed" or not message.content.strip():
        raise HTTPException(status_code=400, detail="Voice message must be transcribed before reply generation")

    character = db.get(Character, message.character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return generate_voice_response(db, character, message)


@router.post("/messages/{message_id}/retry-generation", response_model=MessageRead)
def retry_voice_generation(message_id: str, db: Session = Depends(get_db)) -> Message:
    message = db.get(Message, message_id)
    if not message or message.role != "assistant":
        raise HTTPException(status_code=404, detail="Assistant message not found")
    if not message.voice_generation_can_retry:
        raise HTTPException(status_code=400, detail="Voice generation is not available for retry")

    message.voice_generation_status = "pending"
    message.voice_generation_error = ""
    db.add(message)
    db.commit()
    try:
        attach_prepared_character_voice(message)
        db.add(message)
        db.commit()
        db.refresh(message)
        return message
    except (TTSConfigurationError, TTSProviderError, VoiceStorageError) as exc:
        db.rollback()
        db.refresh(message)
        message.voice_generation_status = "failed"
        message.voice_generation_error = str(exc)
        db.add(message)
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        db.refresh(message)
        message.voice_generation_status = "failed"
        message.voice_generation_error = str(exc) or exc.__class__.__name__
        db.add(message)
        db.commit()
        raise HTTPException(
            status_code=503,
            detail=str(exc) or exc.__class__.__name__,
        ) from exc


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


@router.get("/catalog", response_model=list[VoiceOptionRead])
def voice_catalog() -> list[dict[str, str]]:
    return catalog_payload()


@router.get("/constraints", response_model=VoiceUploadConstraintsRead)
def voice_upload_constraints() -> VoiceUploadConstraintsRead:
    return VoiceUploadConstraintsRead(
        max_duration_ms=MAX_VOICE_DURATION_MS,
        max_file_size_bytes=MAX_VOICE_BYTES,
        accepted_mime_types=sorted(SUPPORTED_AUDIO_TYPES),
    )


@router.post("/preview")
def preview_voice(payload: VoicePreviewRequest) -> Response:
    try:
        speech = synthesize_voice_preview(payload.voice_id)
    except TTSConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TTSProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content=speech.audio_bytes, media_type=speech.mime_type)
