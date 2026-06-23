from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    gender: Mapped[str] = mapped_column(String, default="unspecified")
    relationship_mode: Mapped[str] = mapped_column(String, default="companion")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="characters")
    profile = relationship("CharacterProfile", back_populates="character", uselist=False, cascade="all, delete-orphan")
    state = relationship("CharacterState", back_populates="character", uselist=False, cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="character", cascade="all, delete-orphan")


class CharacterProfile(Base):
    __tablename__ = "character_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    character_id: Mapped[str] = mapped_column(String, ForeignKey("characters.id"), unique=True, index=True)
    personality_description: Mapped[str] = mapped_column(Text, default="")
    communication_style: Mapped[str] = mapped_column(Text, default="")
    background_story: Mapped[str] = mapped_column(Text, default="")
    boundaries: Mapped[str] = mapped_column(Text, default="")
    voice_id: Mapped[str] = mapped_column(String, default="mock-voice")

    character = relationship("Character", back_populates="profile")


class CharacterState(Base):
    __tablename__ = "character_states"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    character_id: Mapped[str] = mapped_column(String, ForeignKey("characters.id"), unique=True, index=True)
    mood: Mapped[str] = mapped_column(String, default="calm")
    trust_level: Mapped[int] = mapped_column(Integer, default=10)
    attachment_level: Mapped[int] = mapped_column(Integer, default=5)
    energy_level: Mapped[int] = mapped_column(Integer, default=80)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    character = relationship("Character", back_populates="state")
