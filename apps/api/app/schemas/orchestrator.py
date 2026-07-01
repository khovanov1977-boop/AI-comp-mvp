from datetime import datetime

from pydantic import BaseModel


MEMORY_CATEGORIES = ("user_fact", "preference", "life_event", "relationship_note", "system_note")


class OrchestratorProfileContext(BaseModel):
    personality_description: str
    communication_style: str
    biography: str
    boundaries: str
    likes: str
    dislikes: str
    language: str
    user_nickname: str


class OrchestratorStateContext(BaseModel):
    mood: str
    trust: int
    attachment: int
    energy: int


class OrchestratorMemoryItem(BaseModel):
    id: str
    content: str
    importance: int
    created_at: datetime


class OrchestratorMessageContext(BaseModel):
    role: str
    content: str
    message_type: str
    created_at: datetime


class OrchestratorContext(BaseModel):
    character_id: str
    character_name: str
    relationship_mode: str
    profile: OrchestratorProfileContext
    state: OrchestratorStateContext
    memory: dict[str, list[OrchestratorMemoryItem]]
    recent_messages: list[OrchestratorMessageContext]
    current_user_message: str


class OrchestratorContextDebugRequest(BaseModel):
    character_id: str
    message: str
