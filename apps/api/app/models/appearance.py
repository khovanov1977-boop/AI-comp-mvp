from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CharacterAppearance(Base):
    __tablename__ = "character_appearances"

    character_id: Mapped[str] = mapped_column(String, ForeignKey("characters.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    counts: Mapped[dict] = mapped_column(JSON, default=lambda: {"face": 1, "body": 1, "clothing": 1})
    selections: Mapped[dict] = mapped_column(JSON, default=dict)
    published: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __mapper_args__ = {"version_id_col": revision}


class AppearanceCandidate(Base):
    """Completed provider outputs only; public APIs cannot insert arbitrary images."""

    __tablename__ = "appearance_candidates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    character_id: Mapped[str] = mapped_column(String, ForeignKey("characters.id"), index=True)
    stage: Mapped[str] = mapped_column(String)
    asset_id: Mapped[str] = mapped_column(String, ForeignKey("media_assets.id"))
    input_context: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ImageGenerationJob(Base):
    __tablename__ = "image_generation_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    character_id: Mapped[str] = mapped_column(String, ForeignKey("characters.id"), index=True)
    # A unique nullable key serializes requests per character, also across API workers.
    active_key: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    retry_of: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    stage: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    input_context: Mapped[dict] = mapped_column(JSON)
    prompt: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="queued")
    outputs: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
