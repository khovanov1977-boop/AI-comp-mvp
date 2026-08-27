from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CharacterCreate(BaseModel):
    name: str
    gender: str = "unspecified"
    relationship_mode: str = "companion"
    personality_description: str = ""
    communication_style: str = ""
    background_story: str = ""
    biography: str = ""
    boundaries: str = ""
    likes: str = ""
    dislikes: str = ""
    language: str = "ru"
    user_nickname: str = ""
    user_city: str = ""
    user_country: str = ""
    user_timezone: str = "Europe/Moscow"
    user_language: str = "ru"
    warmth: int = Field(default=50, ge=0, le=100)
    initiative: int = Field(default=50, ge=0, le=100)
    playfulness: int = Field(default=50, ge=0, le=100)
    directness: int = Field(default=50, ge=0, le=100)
    emotionality: int = Field(default=50, ge=0, le=100)
    rationality: int = Field(default=50, ge=0, le=100)


class CharacterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    gender: str
    relationship_mode: str
    personality_description: str
    communication_style: str
    background_story: str
    biography: str
    boundaries: str
    likes: str
    dislikes: str
    language: str
    user_nickname: str
    user_city: str
    user_country: str
    user_timezone: str
    user_language: str
    warmth: int
    initiative: int
    playfulness: int
    directness: int
    emotionality: int
    rationality: int
    created_at: datetime


class CharacterUpdate(BaseModel):
    relationship_mode: str | None = None
    personality_description: str | None = None
    communication_style: str | None = None
    warmth: int | None = Field(default=None, ge=0, le=100)
    initiative: int | None = Field(default=None, ge=0, le=100)
    playfulness: int | None = Field(default=None, ge=0, le=100)
    directness: int | None = Field(default=None, ge=0, le=100)
    emotionality: int | None = Field(default=None, ge=0, le=100)
    rationality: int | None = Field(default=None, ge=0, le=100)
