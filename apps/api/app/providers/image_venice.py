"""Venice Qwen image pair. One request per output, with no automatic retries."""

import base64
import binascii
import json

import httpx

from app.config import Settings, settings
from app.providers.image_openrouter import (
    GeneratedImage, ImageProviderError, MAX_IMAGE_BYTES, MAX_RESPONSE_BYTES,
    _error_diagnostic,
)

VENICE_BASE_URL = "https://api.venice.ai/api/v1"


def venice_configuration_error(config: Settings = settings) -> str:
    if config.image_provider != "venice":
        return "Генерация Venice выключена. Укажите IMAGE_PROVIDER=venice в .env."
    if not config.venice_api_key.strip():
        return "Укажите VENICE_API_KEY в .env."
    if config.venice_image_model.strip() != "qwen-image-3" or config.venice_image_edit_model.strip() != "qwen-edit-uncensored":
        return "Для проверенной связки укажите VENICE_IMAGE_MODEL=qwen-image-3 и VENICE_IMAGE_EDIT_MODEL=qwen-edit-uncensored."
    if not 10 <= config.image_timeout_seconds <= 600:
        return "IMAGE_TIMEOUT_SECONDS должен быть от 10 до 600 секунд."
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

    def generate(self, *, model: str, prompt: str, references: list[bytes],
                 provider_options: dict[str, dict] | None = None) -> GeneratedImage:
        if provider_options:
            raise ImageProviderError("Дополнительные параметры провайдера Venice не поддерживаются.")
        if not references and model == self.generate_model:
            endpoint = "image/generate"
            payload = {"model": model, "prompt": prompt, "aspect_ratio": "2:3", "resolution": "1K",
                       "format": "png", "variants": 1, "safe_mode": False, "enhance_prompt": False}
        elif len(references) == 1 and model == self.edit_model:
            endpoint = "image/edit"
            payload = {"model": model, "prompt": prompt,
                       "image": base64.b64encode(references[0]).decode("ascii"),
                       "aspect_ratio": "2:3", "output_format": "png",
                       "safe_mode": False, "enhance_prompt": False}
        else:
            raise ImageProviderError("Для Venice нужен один референс на этапе редактирования и ни одного при создании лица.")
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
                    raise ImageProviderError(
                        f"Venice вернул ошибку HTTP {response.status_code}. Автоповтор отключён.",
                        unknown_outcome=response.status_code >= 500, diagnostic=diagnostic)
                if response.status_code != 200:
                    raise ImageProviderError("Неожиданный ответ Venice; повтор не выполнен.", unknown_outcome=True)
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
                if "image/png" not in content_type.lower():
                    raise ValueError("Expected PNG response")
                data = body
            if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > MAX_IMAGE_BYTES:
                raise ValueError("Invalid PNG")
            return GeneratedImage(data=data)
        except ImageProviderError:
            raise
        except httpx.RequestError:
            raise ImageProviderError("Связь с Venice прервана. Результат запроса неизвестен; автоматического повтора нет.", unknown_outcome=True) from None
        except (ValueError, TypeError, AttributeError, KeyError, binascii.Error):
            raise ImageProviderError("Venice не вернул корректное изображение. Автоматического повтора нет.", unknown_outcome=True) from None
