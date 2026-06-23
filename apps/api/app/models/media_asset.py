from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    character_id: Mapped[str] = mapped_column(String, ForeignKey("characters.id"), index=True)
    media_type: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    prompt: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String, default="mock")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IdentityReference(Base):
    __tablename__ = "identity_references"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    character_id: Mapped[str] = mapped_column(String, ForeignKey("characters.id"), index=True)
    reference_type: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    prompt: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
