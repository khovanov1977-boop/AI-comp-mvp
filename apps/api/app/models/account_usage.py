from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AccountUsage(Base):
    """Lifetime beta allowance, retained when a character or chat is deleted."""

    __tablename__ = "account_usage"

    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), primary_key=True)
    images_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    videos_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text_messages_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    voice_messages_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
