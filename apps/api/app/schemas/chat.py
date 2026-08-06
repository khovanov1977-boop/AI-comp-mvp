from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CharacterStateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mood: str
    trust_level: int
    attachment_level: int
    energy_level: int


class ChatRequest(BaseModel):
    character_id: str
    message: str


class ChatRetryRequest(BaseModel):
    character_id: str


class ChatResponse(BaseModel):
    reply: str
    character_state: CharacterStateRead


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    character_id: str
    role: str
    content: str
    message_type: str
    created_at: datetime


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    character_id: str
    memory_type: str
    content: str
    importance: int
    created_at: datetime


class UserContextRead(BaseModel):
    display_name: str
    city: str
    country: str
    timezone: str
    language: str


class SceneContextRead(BaseModel):
    character_id: str
    presence_mode: str
    location_name: str
    location_description: str
    user_position: str
    character_position: str


class CompanionContextRead(BaseModel):
    character_state: CharacterStateRead
    user_context: UserContextRead
    scene_context: SceneContextRead
    memories: list[MemoryRead]
