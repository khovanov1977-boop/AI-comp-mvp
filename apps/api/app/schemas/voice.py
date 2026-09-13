from pydantic import BaseModel


class VoiceOptionRead(BaseModel):
    id: str
    gender: str
    age_group: str
    description: str


class VoicePreviewRequest(BaseModel):
    voice_id: str


class VoiceUploadConstraintsRead(BaseModel):
    max_duration_ms: int
    max_file_size_bytes: int
    accepted_mime_types: list[str]
