from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

AppearanceStage = Literal["face", "body", "clothing"]


class AppearanceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gender: Literal["female", "male", "non_binary"]
    style: Literal["photo", "cartoon", "anime", "3d", "digital_painting", "comic", "watercolor"] | None = None
    appearance_type: Literal["european", "african", "asian", "arab", "latin_american", "caucasus"] | None = None
    age: int | None = Field(default=None, ge=1, le=120, strict=True)
    hair_color: str | None = Field(default=None, max_length=100)
    eye_color: str | None = Field(default=None, max_length=100)
    hairstyle: str | None = Field(default=None, max_length=300)
    glasses: bool | None = Field(default=None, strict=True)
    face_details: str | None = Field(default=None, max_length=1000)
    body_type: Literal["ordinary", "fit", "athletic", "full", "fat"] | None = None
    face_adjustment: Literal["allow", "preserve"] | None = None
    body_details: str | None = Field(default=None, max_length=1000)
    clothing: str | None = Field(default=None, max_length=1000)
    clothing_details: str | None = Field(default=None, max_length=1000)

    @field_validator("hair_color", "eye_color", "hairstyle", "face_details", "body_details", "clothing", "clothing_details", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        return value.strip() or None if isinstance(value, str) else value


class AppearanceSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1, strict=True)
    candidate_id: str


class AppearancePublish(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1, strict=True)
    confirm_gender_change: bool = False


class AppearanceGenerate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    expected_revision: int = Field(ge=0, strict=True)
    settings: AppearanceSettings | None = None
    count: int | None = Field(default=None, ge=1, le=3, strict=True)
    retry_of: UUID | None = None
    confirm_unknown_retry: bool = False
