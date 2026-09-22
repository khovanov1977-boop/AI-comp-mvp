from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
from uuid import uuid4
import warnings

from PIL import Image, UnidentifiedImageError

from app.providers.image_openrouter import MAX_IMAGE_BYTES

IMAGE_STORAGE_ROOT = Path(__file__).resolve().parents[2] / "data" / "media"
MAX_PIXELS = 16_777_216


class ImageStorageError(ValueError):
    pass


def character_storage_key(character_id: str) -> str:
    return sha256(character_id.encode("utf-8")).hexdigest()[:24]


def normalized_png(data: bytes) -> bytes:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ImageStorageError("Изображение пустое или превышает 20 МБ.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in {"PNG", "JPEG", "WEBP"} or source.width * source.height > MAX_PIXELS:
                    raise ImageStorageError("Недопустимый формат или размер изображения.")
                source.load()
                output = BytesIO()
                source.convert("RGB").save(output, format="PNG")
        png = output.getvalue()
        if len(png) > MAX_IMAGE_BYTES:
            raise ImageStorageError("Изображение превышает допустимый размер.")
        return png
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageStorageError("Модель вернула повреждённое или неподдерживаемое изображение.") from None


def resolve_image_file(url: str, character_id: str | None = None) -> Path | None:
    parts = PurePosixPath(url).parts
    if len(parts) != 4 or parts[:2] != ("/", "media-files"):
        return None
    key, filename = parts[2:]
    if character_id and key != character_storage_key(character_id):
        return None
    if len(key) != 24 or any(c not in "0123456789abcdef" for c in key):
        return None
    if "\\" in filename or not filename.endswith(".png"):
        return None
    path = (IMAGE_STORAGE_ROOT / key / filename).resolve()
    return path if path.is_relative_to(IMAGE_STORAGE_ROOT.resolve()) else None


def save_image(character_id: str, data: bytes) -> str:
    png = normalized_png(data)
    url = f"/media-files/{character_storage_key(character_id)}/{uuid4()}.png"
    path = resolve_image_file(url, character_id)
    if path is None:
        raise ImageStorageError("Не удалось определить путь изображения.")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as output:
            output.write(png)
    except OSError:
        path.unlink(missing_ok=True)
        raise ImageStorageError("Не удалось сохранить изображение на диске.") from None
    return url


def read_image(url: str, character_id: str) -> bytes:
    path = resolve_image_file(url, character_id)
    if path is None or not path.is_file():
        raise ImageStorageError("Файл выбранного референса отсутствует.")
    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise ImageStorageError("Референс превышает допустимый размер.")
    return path.read_bytes()


def delete_image(url: str, character_id: str) -> None:
    path = resolve_image_file(url, character_id)
    if path:
        path.unlink(missing_ok=True)


def delete_character_image_files(character_id: str) -> None:
    directory = (IMAGE_STORAGE_ROOT / character_storage_key(character_id)).resolve()
    if not directory.is_relative_to(IMAGE_STORAGE_ROOT.resolve()) or not directory.is_dir():
        return
    for path in directory.iterdir():
        if path.is_file() and path.suffix == ".png":
            path.unlink(missing_ok=True)
    if not any(directory.iterdir()):
        directory.rmdir()
