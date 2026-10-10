from pathlib import Path, PurePosixPath
from uuid import uuid4

from app.providers.video_venice import MAX_VIDEO_BYTES
from app.services.image_storage import IMAGE_STORAGE_ROOT, character_storage_key


def resolve_video_file(url: str, character_id: str) -> Path | None:
    parts = PurePosixPath(url).parts
    if len(parts) != 4 or parts[:3] != ("/", "media-files", character_storage_key(character_id)):
        return None
    filename = parts[3]
    if not filename.endswith(".mp4") or "\\" in filename or "/" in filename:
        return None
    path = (IMAGE_STORAGE_ROOT / parts[2] / filename).resolve()
    return path if path.is_relative_to(IMAGE_STORAGE_ROOT.resolve()) else None


def save_video(character_id: str, data: bytes) -> str:
    if not data or len(data) > MAX_VIDEO_BYTES or b"ftyp" not in data[:16]:
        raise ValueError("Получен повреждённый или слишком большой видеофайл.")
    url = f"/media-files/{character_storage_key(character_id)}/{uuid4()}.mp4"
    path = resolve_video_file(url, character_id)
    if path is None:
        raise ValueError("Не удалось определить путь видео.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        output.write(data)
    return url


def delete_video(url: str, character_id: str) -> None:
    path = resolve_video_file(url, character_id)
    if path:
        path.unlink(missing_ok=True)
