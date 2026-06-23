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
