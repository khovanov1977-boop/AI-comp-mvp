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


class OrchestratorUserContext(BaseModel):
    display_name: str
    city: str
    country: str
    timezone: str
    language: str
    local_datetime: datetime
    local_datetime_iso: str
    local_date: str
    local_time: str
    weekday: str
    time_of_day: str
    daylight_context: str


class OrchestratorSceneContext(BaseModel):
    presence_mode: str
    location_name: str
    location_description: str
    user_position: str
    character_position: str
    can_use_physical_touch: bool
    can_share_immediate_physical_space: bool


class OrchestratorWorldStateContext(BaseModel):
    reality_summary: str
    location_type: str
    posture_summary: str
    physical_touch_policy: str
    shared_space_policy: str
    movement_policy: str
    allowed_interaction_modes: list[str]


class OrchestratorLanguageContext(BaseModel):
    slang_terms: dict[str, str]
    smileys: dict[str, str]
    typo_hints: dict[str, str]
    has_colloquial_language: bool
    guidance: str


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
    character_gender: str
    relationship_mode: str
    profile: OrchestratorProfileContext
    state: OrchestratorStateContext
    user_context: OrchestratorUserContext
    scene_context: OrchestratorSceneContext
    world_state: OrchestratorWorldStateContext
    language_context: OrchestratorLanguageContext
    memory: dict[str, list[OrchestratorMemoryItem]]
    recent_messages: list[OrchestratorMessageContext]
    current_user_message: str


class OrchestratorContextDebugRequest(BaseModel):
    character_id: str
    message: str
