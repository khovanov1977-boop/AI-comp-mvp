from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SceneImageJob(Base):
    __tablename__ = "scene_image_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    character_id: Mapped[str] = mapped_column(String, ForeignKey("characters.id"), index=True)
    active_key: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    user_message_id: Mapped[str] = mapped_column(String, ForeignKey("messages.id"))
    assistant_message_id: Mapped[str] = mapped_column(String, ForeignKey("messages.id"))
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    reference_url: Mapped[str] = mapped_column(Text)
    prompt: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="queued")
    cost_usd: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
