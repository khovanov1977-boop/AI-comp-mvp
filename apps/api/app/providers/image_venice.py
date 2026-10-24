"""Venice image generation and single-reference edits, without automatic retries."""

import base64
import binascii
from io import BytesIO
import json

import httpx
from PIL import Image, UnidentifiedImageError

from app.config import Settings, settings
from app.providers.image_openrouter import (
    GeneratedImage, ImageProviderError, MAX_IMAGE_BYTES, MAX_RESPONSE_BYTES,
    _error_diagnostic,
)

VENICE_BASE_URL = "https://api.venice.ai/api/v1"
IMAGE_MODEL_PAIRS = {
    ("grok-imagine-image-2-0", "grok-imagine-image-2-0-edit"),
    ("qwen-image-3", "qwen-edit-uncensored"),  # Also used for new in-chat context photos.
}
GENERATE_MODELS = {pair[0] for pair in IMAGE_MODEL_PAIRS}
EDIT_MODELS = {pair[1] for pair in IMAGE_MODEL_PAIRS}


def _as_png(data: bytes) -> bytes:
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds size limit")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data
    # Grok Imagine 2.0 currently returns JPEG even when PNG is requested.
    if not data.startswith(b"\xff\xd8\xff"):
        raise ValueError("Unsupported image format")
    with Image.open(BytesIO(data)) as image:
        if image.format != "JPEG" or image.width * image.height > 16_000_000:
            raise ValueError("Invalid image dimensions or format")
        output = BytesIO()
        image.convert("RGB").save(output, format="PNG")
        converted = output.getvalue()
    if len(converted) > MAX_IMAGE_BYTES:
        raise ValueError("Converted image exceeds size limit")
    return converted


def venice_configuration_error(config: Settings = settings) -> str:
    if config.image_provider != "venice":
        return "Создание изображений не настроено."
    if not config.venice_api_key.strip():
        return "Не настроен доступ к сервису создания изображений."
    if (config.venice_image_model.strip(), config.venice_image_edit_model.strip()) not in IMAGE_MODEL_PAIRS:
        return "Некорректно настроен способ создания изображений."
    if config.venice_clothing_image_edit_model.strip() not in EDIT_MODELS:
        return "Некорректно настроена модель создания одежды."
    if not 10 <= config.image_timeout_seconds <= 600:
        return "Некорректно настроено время ожидания создания изображений."
    return ""


class VeniceImageProvider:
    def __init__(self, config: Settings = settings, client: httpx.Client | None = None):
        error = venice_configuration_error(config)
        if error:
            raise ImageProviderError(error)
        self.api_key = config.venice_api_key.strip()
        self.timeout = config.image_timeout_seconds
        self.generate_model = config.venice_image_model.strip()
        self.edit_model = config.venice_image_edit_model.strip()
        self.client = client

    def generate(self, *, model: str, prompt: str, references: list[bytes], negative_prompt: str | None = None,
                 provider_options: dict[str, dict] | None = None) -> GeneratedImage:
        if provider_options:
            raise ImageProviderError("Дополнительные параметры создания изображений не поддерживаются.")
        if not references and model in GENERATE_MODELS:
            endpoint = "image/generate"
            payload = {"model": model, "prompt": prompt, "aspect_ratio": "2:3", "resolution": "1K",
                       "format": "png", "variants": 1, "safe_mode": False, "enhance_prompt": False}
            if model == "grok-imagine-image-2-0":
                payload["quality"] = "medium"
            if negative_prompt:
                payload["negative_prompt"] = negative_prompt
        elif len(references) == 1 and model in EDIT_MODELS:
            if negative_prompt:
                raise ImageProviderError("Отрицательный промпт поддерживается только при создании изображения.")
            endpoint = "image/edit"
            payload = {"model": model, "prompt": prompt,
                       "image": base64.b64encode(references[0]).decode("ascii"),
                       "aspect_ratio": "2:3", "output_format": "png",
                       "safe_mode": False, "enhance_prompt": False}
            if model == "grok-imagine-image-2-0-edit":
                payload["resolution"] = "1K"
        else:
            raise ImageProviderError("При редактировании нужен один референс, а при создании лица референс не нужен.")
        if self.client is not None:
            return self._send(self.client, endpoint, payload)
        with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
            return self._send(client, endpoint, payload)

    def _send(self, client: httpx.Client, endpoint: str, payload: dict) -> GeneratedImage:
        try:
            with client.stream("POST", f"{VENICE_BASE_URL}/{endpoint}", json=payload,
                               headers={"Authorization": f"Bearer {self.api_key}"},
                               timeout=self.timeout, follow_redirects=False) as response:
                if response.status_code >= 400:
                    diagnostic = _error_diagnostic(response, self.api_key)
                    if response.status_code == 422:
                        code = diagnostic.get("code")
                        if code == "IMAGE_TOO_LARGE":
                            message = "Референс слишком велик для модели (HTTP 422). Выберите другое исходное изображение."
                        else:
                            message = ("Модель отклонила запрос изображения (HTTP 422). "
                                       "Измените описание или референс и создайте новые варианты; повтор без изменений может снова завершиться ошибкой.")
                    else:
                        message = f"Ошибка создания изображения (HTTP {response.status_code}). Автоповтор отключён."
                    raise ImageProviderError(
                        message,
                        unknown_outcome=response.status_code >= 500, diagnostic=diagnostic)
                if response.status_code != 200:
                    raise ImageProviderError("Неожиданный ответ при создании изображения; повтор не выполнен.", unknown_outcome=True)
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        raise ImageProviderError("Ответ модели превышает допустимый размер.", unknown_outcome=True)
                    chunks.append(chunk)
                content_type = response.headers.get("content-type", "")
            body = b"".join(chunks)
            if endpoint == "image/generate":
                images = json.loads(body).get("images", [])
                if len(images) != 1 or not isinstance(images[0], str):
                    raise ValueError("Expected one base64 image")
                data = base64.b64decode(images[0].split(",", 1)[-1], validate=True)
            else:
                if not any(mime in content_type.lower() for mime in ("image/png", "image/jpeg", "image/jpg")):
                    raise ValueError("Expected image response")
                data = body
            return GeneratedImage(data=_as_png(data))
        except ImageProviderError:
            raise
        except httpx.RequestError:
            raise ImageProviderError("Связь прервана. Результат запроса неизвестен; автоматического повтора нет.", unknown_outcome=True) from None
        except (ValueError, TypeError, AttributeError, KeyError, binascii.Error, UnidentifiedImageError, OSError):
            raise ImageProviderError("Не получено корректное изображение. Автоматического повтора нет.", unknown_outcome=True) from None
