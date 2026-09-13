from pydantic import BaseModel


class VoiceOptionRead(BaseModel):
    id: str
    gender: str
    age_group: str
    description: str


class VoicePreviewRequest(BaseModel):
    voice_id: str
