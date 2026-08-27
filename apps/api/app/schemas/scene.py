from datetime import datetime

from pydantic import BaseModel, ConfigDict


PRESENCE_MODES = {"remote_chat", "same_place", "virtual_roleplay"}


class SceneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    character_id: str
    presence_mode: str
    location_name: str
    location_description: str
    time_description: str
    user_position: str
    character_position: str
    context_started_at: datetime | None
    updated_at: datetime


class SceneUpdate(BaseModel):
    character_id: str
    presence_mode: str = "remote_chat"
    location_name: str = "Private chat"
    location_description: str = ""
    time_description: str = ""
    user_position: str = "at their own place"
    character_position: str = "at their own place"
    start_new_scene: bool = False
    previous_scene_summary: str = ""
