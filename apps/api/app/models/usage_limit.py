from datetime import date
from uuid import uuid4

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UsageLimit(Base):
    __tablename__ = "usage_limits"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    text_messages_count: Mapped[int] = mapped_column(Integer, default=0)
    images_count: Mapped[int] = mapped_column(Integer, default=0)
    videos_count: Mapped[int] = mapped_column(Integer, default=0)
    voice_messages_count: Mapped[int] = mapped_column(Integer, default=0)
