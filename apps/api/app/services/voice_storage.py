from hashlib import sha256
from pathlib import Path, PurePosixPath
from uuid import uuid4


VOICE_STORAGE_ROOT = Path(__file__).resolve().parents[2] / "data" / "voice"
MAX_VOICE_BYTES = 10 * 1024 * 1024
MAX_VOICE_DURATION_MS = 120_000

SUPPORTED_AUDIO_TYPES = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}


class VoiceStorageError(ValueError):
    pass


class VoiceFileTooLargeError(VoiceStorageError):
    pass


def normalize_audio_type(content_type: str) -> str:
    return content_type.partition(";")[0].strip().lower()


def character_storage_key(character_id: str) -> str:
    return sha256(character_id.encode("utf-8")).hexdigest()[:24]


def save_voice_file(character_id: str, audio_bytes: bytes, content_type: str) -> tuple[str, str]:
    mime_type = normalize_audio_type(content_type)
    extension = SUPPORTED_AUDIO_TYPES.get(mime_type)
    if not extension:
        raise VoiceStorageError("Unsupported audio format")
    if not audio_bytes:
        raise VoiceStorageError("Voice message is empty")
    if len(audio_bytes) > MAX_VOICE_BYTES:
        raise VoiceFileTooLargeError("Voice message is larger than 10 MB")

    storage_key = character_storage_key(character_id)
    character_directory = VOICE_STORAGE_ROOT / storage_key
    character_directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4()}{extension}"
    (character_directory / filename).write_bytes(audio_bytes)
    return f"/voice-files/{storage_key}/{filename}", mime_type


def delete_voice_file(audio_url: str) -> None:
    path = PurePosixPath(audio_url)
    if len(path.parts) != 4 or path.parts[:2] != ("/", "voice-files"):
        return

    storage_key, filename = path.parts[2:]
    if Path(filename).name != filename or Path(storage_key).name != storage_key:
        return

    file_path = (VOICE_STORAGE_ROOT / storage_key / filename).resolve()
    storage_root = VOICE_STORAGE_ROOT.resolve()
    if not file_path.is_relative_to(storage_root):
        return
    file_path.unlink(missing_ok=True)
    character_directory = file_path.parent
    if character_directory.exists() and not any(character_directory.iterdir()):
        character_directory.rmdir()


def delete_character_voice_files(character_id: str) -> None:
    character_directory = VOICE_STORAGE_ROOT / character_storage_key(character_id)
    if not character_directory.exists():
        return
    for path in character_directory.iterdir():
        if path.is_file():
            path.unlink(missing_ok=True)
    if not any(character_directory.iterdir()):
        character_directory.rmdir()
