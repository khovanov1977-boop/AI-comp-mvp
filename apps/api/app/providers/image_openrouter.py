"""OpenRouter Image API, one output per call; deliberately no automatic retries."""

import base64
import binascii
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json

import httpx

from app.config import Settings, settings

MAX_RESPONSE_BYTES = 32 * 1024 * 1024
MAX_IMAGE_BYTES = 20 * 1024 * 1024


class ImageProviderError(Exception):
    def __init__(self, message: str, *, unknown_outcome: bool = False):
        super().__init__(message)
        self.unknown_outcome = unknown_outcome


@dataclass(frozen=True)
class GeneratedImage:
    data: bytes
    cost_usd: Decimal | None = None


def image_configuration_error(config: Settings = settings) -> str:
    if config.image_provider != "openrouter":
        return "Генерация выключена. Укажите IMAGE_PROVIDER=openrouter в .env."
    if config.image_base_url.rstrip("/") != "https://openrouter.ai/api/v1":
        return "Для OpenRouter требуется IMAGE_BASE_URL=https://openrouter.ai/api/v1."
    if not config.image_model.strip():
        return "Укажите IMAGE_MODEL в .env."
    if not config.effective_image_api_key:
        return "Нужен существующий LLM_API_KEY или IMAGE_API_KEY для OpenRouter."
    if not 10 <= config.image_timeout_seconds <= 600:
        return "IMAGE_TIMEOUT_SECONDS должен быть от 10 до 600 секунд."
    return ""


class OpenRouterImageProvider:
    def __init__(self, config: Settings = settings, client: httpx.Client | None = None):
        error = image_configuration_error(config)
        if error:
            raise ImageProviderError(error)
        self.base_url = config.image_base_url.rstrip("/")
        self.api_key = config.effective_image_api_key
        self.timeout = config.image_timeout_seconds
        self.client = client

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        references: list[bytes],
        provider_options: dict[str, dict] | None = None,
    ) -> GeneratedImage:
        payload = {
            "model": model, "prompt": prompt, "n": 1, "size": "1024x1024",
            "output_format": "png", "provider": {"allow_fallbacks": False},
        }
        if provider_options:
            payload["provider"]["options"] = provider_options
        if references:
            payload["input_references"] = [
                {"type": "image_url", "image_url": {
                    "url": "data:image/png;base64," + base64.b64encode(data).decode("ascii"),
                }} for data in references
            ]
        if self.client is not None:
            return self._send(self.client, payload)
        with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
            return self._send(client, payload)

    def _send(self, client: httpx.Client, payload: dict) -> GeneratedImage:
        try:
            with client.stream("POST", f"{self.base_url}/images", json=payload,
                               headers={"Authorization": f"Bearer {self.api_key}"}, timeout=self.timeout,
                               follow_redirects=False) as response:
                if response.status_code >= 400:
                    messages = {
                        400: "OpenRouter отклонил запрос (HTTP 400). Автоповтор отключён; проверьте параметры или повторите только неполученные варианты.",
                        401: "OpenRouter отклонил API-ключ.",
                        402: "На счёте OpenRouter недостаточно средств или достигнут лимит ключа.",
                        403: "OpenRouter отказал в доступе к генерации.",
                        404: "Модель или Image API недоступны. Проверьте IMAGE_MODEL.",
                        429: "Достигнут лимит частоты запросов OpenRouter. Автоповтор отключён.",
                    }
                    raise ImageProviderError(messages.get(response.status_code,
                        f"OpenRouter вернул ошибку HTTP {response.status_code}. Автоповтор отключён."),
                        unknown_outcome=response.status_code >= 500)
                if response.status_code != 200:
                    raise ImageProviderError("Неожиданный ответ OpenRouter; повтор не выполнен.", unknown_outcome=True)
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        raise ImageProviderError("Ответ модели превышает допустимый размер.", unknown_outcome=True)
                    chunks.append(chunk)
            body = json.loads(b"".join(chunks))
            outputs = body.get("data", [])
            if len(outputs) != 1 or not isinstance(outputs[0].get("b64_json"), str):
                raise ValueError("Expected one base64 image")
            data = base64.b64decode(outputs[0]["b64_json"], validate=True)
            if not data or len(data) > MAX_IMAGE_BYTES:
                raise ValueError("Invalid image length")
            cost = None
            raw_cost = (body.get("usage") or {}).get("cost")
            if raw_cost is not None:
                try:
                    value = Decimal(str(raw_cost))
                    if value.is_finite() and value >= 0:
                        cost = value
                except InvalidOperation:
                    pass
            return GeneratedImage(data=data, cost_usd=cost)
        except ImageProviderError:
            raise
        except httpx.RequestError:
            raise ImageProviderError("Связь с OpenRouter прервана. Результат запроса неизвестен; автоматического повтора нет.", unknown_outcome=True) from None
        except (ValueError, TypeError, AttributeError, KeyError, binascii.Error):
            raise ImageProviderError("OpenRouter не вернул корректное изображение. Автоматического повтора нет.", unknown_outcome=True) from None
