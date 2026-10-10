from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class VideoRequest(BaseModel):
    request_id: UUID
    mode: Literal["animate_photo", "reference_video"]
    prompt: str = Field(min_length=1, max_length=1800)
    aspect_ratio: Literal["auto", "16:9", "9:16", "4:3", "3:4", "1:1", "2:3"] = "auto"
    source_message_id: str | None = None
    duration: Literal["5s", "10s", "15s"] = "5s"
    resolution: Literal["480p", "720p", "1080p"] = "720p"
    accepted_quote_usd: str


class VideoQuoteRequest(BaseModel):
    mode: Literal["animate_photo", "reference_video"]
    duration: Literal["5s", "10s", "15s"] = "5s"
    resolution: Literal["480p", "720p", "1080p"] = "720p"
    aspect_ratio: Literal["auto", "16:9", "9:16", "4:3", "3:4", "1:1", "2:3"] = "auto"


class VideoQuoteRead(BaseModel):
    model: str
    available: bool
    price_usd: str | None
    unavailable_reason: str = ""


class VideoJobRead(BaseModel):
    id: str
    mode: str
    model: str
    status: str
    quote_usd: str
    aspect_ratio: str
    error: str
    created_at: datetime
