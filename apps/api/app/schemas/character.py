from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
    created_at: datetime
