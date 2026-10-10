"""Venice video catalog, quotes, queue and retrieval. Queue is never retried."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import httpx

from app.config import Settings, settings

BASE_URL = "https://api.venice.ai/api/v1"
MAX_VIDEO_BYTES = 100 * 1024 * 1024


class VeniceVideoError(Exception):
    def __init__(self, message: str, *, unknown_outcome: bool = False):
        super().__init__(message)
        self.unknown_outcome = unknown_outcome


@dataclass(frozen=True)
class QueuedVideo:
    model: str
    queue_id: str
    download_url: str = ""


class VeniceVideoProvider:
    def __init__(self, config: Settings = settings):
        if not config.venice_api_key.strip():
            raise VeniceVideoError("Не настроен доступ к сервису создания видео.")
        self.headers = {"Authorization": f"Bearer {config.venice_api_key.strip()}"}

    def available_models(self) -> set[str]:
        try:
            response = httpx.get(f"{BASE_URL}/models", params={"type": "video"},
                                 headers=self.headers, timeout=20)
            response.raise_for_status()
            return {item["id"] for item in response.json().get("data", [])
                    if item.get("model_spec", {}).get("offline") is False}
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise VeniceVideoError("Не удалось проверить доступность создания видео.") from exc

    def quote(self, model: str, duration: str, resolution: str, aspect_ratio: str = "",
              audio: bool | None = None) -> str:
        payload = {"model": model, "duration": duration, "resolution": resolution}
        if aspect_ratio:
            payload["aspect_ratio"] = aspect_ratio
        if audio is not None:
            payload["audio"] = audio
        try:
            response = httpx.post(f"{BASE_URL}/video/quote", headers=self.headers,
                                  json=payload, timeout=20)
            response.raise_for_status()
            quote = Decimal(str(response.json()["quote"]))
            if quote < 0:
                raise ValueError("negative quote")
            return str(quote)
        except (httpx.HTTPError, ValueError, KeyError, InvalidOperation) as exc:
            raise VeniceVideoError("Не удалось получить стоимость видео.") from exc

    def queue(self, payload: dict) -> QueuedVideo:
        try:
            response = httpx.post(f"{BASE_URL}/video/queue", headers=self.headers,
                                  json=payload, timeout=90)
        except httpx.HTTPError as exc:
            raise VeniceVideoError("Связь прервалась при отправке видео. Результат неизвестен.",
                                   unknown_outcome=True) from exc
        if response.status_code >= 400:
            raise VeniceVideoError(
                f"Не удалось отправить видео (HTTP {response.status_code}).",
                unknown_outcome=response.status_code >= 500,
            )
        try:
            data = response.json()
            return QueuedVideo(model=data["model"], queue_id=data["queue_id"],
                               download_url=data.get("download_url", ""))
        except (ValueError, KeyError, TypeError) as exc:
            raise VeniceVideoError("Запрос принят, но номер задания не получен. Результат неизвестен.",
                                   unknown_outcome=True) from exc

    def retrieve(self, queued: QueuedVideo) -> tuple[str, bytes | None]:
        try:
            with httpx.stream("POST", f"{BASE_URL}/video/retrieve", headers=self.headers,
                              json={"model": queued.model, "queue_id": queued.queue_id}, timeout=90) as response:
                response.raise_for_status()
                if "video/mp4" in response.headers.get("content-type", ""):
                    chunks = []
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_VIDEO_BYTES:
                            raise VeniceVideoError("Видеофайл превышает 100 МБ.")
                        chunks.append(chunk)
                    return "completed", b"".join(chunks)
                response.read()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise VeniceVideoError("Не удалось проверить состояние видео.") from exc
        status = str(data.get("status", "")).upper()
        if status == "COMPLETED" and queued.download_url:
            return "completed", self._download(queued.download_url)
        if status in {"QUEUED", "PROCESSING", "PENDING", "RUNNING"}:
            return "processing", None
        if status in {"FAILED", "ERROR", "CANCELLED"}:
            return "failed", None
        raise VeniceVideoError("Получен неизвестный статус видео.")

    @staticmethod
    def _download(url: str) -> bytes:
        try:
            with httpx.stream("GET", url, timeout=90) as response:
                response.raise_for_status()
                chunks = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_VIDEO_BYTES:
                        raise VeniceVideoError("Видеофайл превышает 100 МБ.")
                    chunks.append(chunk)
                return b"".join(chunks)
        except httpx.HTTPError as exc:
            raise VeniceVideoError("Не удалось скачать готовое видео.") from exc

    def complete(self, queued: QueuedVideo) -> None:
        try:
            httpx.post(f"{BASE_URL}/video/complete", headers=self.headers,
                       json={"model": queued.model, "queue_id": queued.queue_id}, timeout=20)
        except httpx.HTTPError:
            pass
