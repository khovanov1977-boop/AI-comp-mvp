from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.character import CharacterRead


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
    formal_name: str
    preferred_name: str
    casual_name: str
    vocative_name: str
    age: int | None
    city: str
    country: str
    timezone: str
    language: str


class SceneContextRead(BaseModel):
    character_id: str
    presence_mode: str
    location_name: str
    location_description: str
    time_description: str
    user_position: str
    character_position: str
    context_started_at: datetime | None


class MemoryMetaRead(BaseModel):
    total_count: int
    visible_count: int
    visible_limit: int
    counts_by_category: dict[str, int]
    extraction_mode: str
    note: str


class CompanionContextRead(BaseModel):
    character_state: CharacterStateRead
    user_context: UserContextRead
    scene_context: SceneContextRead
    memory_meta: MemoryMetaRead
    memories: list[MemoryRead]


class ChatHistoryClearRead(BaseModel):
    status: str
    character_id: str
    deleted_messages: int
    preserved_memories: int


class ChatExportRead(BaseModel):
    schema_version: int = 1
    exported_at: datetime
    character: CharacterRead
    scene_context: SceneContextRead
    memories: list[MemoryRead]
    messages: list[MessageRead]
