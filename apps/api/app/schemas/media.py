from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MediaRequest(BaseModel):
    character_id: str
    prompt: str = ""


class MediaAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    character_id: str
    media_type: str
    url: str
    prompt: str
    provider: str
    created_at: datetime
