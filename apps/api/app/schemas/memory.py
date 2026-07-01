from datetime import datetime

from pydantic import BaseModel, ConfigDict


MEMORY_CATEGORIES = {
    "user_fact",
    "preference",
    "life_event",
    "relationship_note",
    "system_note",
}


class MemoryCreate(BaseModel):
    character_id: str
    memory_type: str = "user_fact"
    content: str
    importance: int = 2


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    character_id: str
    memory_type: str
    content: str
    importance: int
    created_at: datetime
