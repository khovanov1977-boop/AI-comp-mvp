from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VideoJob(Base):
    __tablename__ = "video_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    character_id: Mapped[str] = mapped_column(String, ForeignKey("characters.id"), index=True)
    active_key: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    mode: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    user_message_id: Mapped[str] = mapped_column(String, ForeignKey("messages.id"))
    assistant_message_id: Mapped[str] = mapped_column(String, ForeignKey("messages.id"))
    source_message_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reference_urls: Mapped[list] = mapped_column(JSON)
    prompt: Mapped[str] = mapped_column(Text)
    provider_prompt: Mapped[str] = mapped_column(Text)
    duration: Mapped[str] = mapped_column(String)
    resolution: Mapped[str] = mapped_column(String)
    aspect_ratio: Mapped[str] = mapped_column(String, default="")
    quote_usd: Mapped[str] = mapped_column(String)
    queue_id: Mapped[str] = mapped_column(String, default="")
    download_url: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="queued")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
