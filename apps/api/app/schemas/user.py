from pydantic import BaseModel, ConfigDict, Field


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
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


class UserProfileUpdate(BaseModel):
    character_id: str
    display_name: str | None = Field(default=None, max_length=100)
    formal_name: str | None = Field(default=None, max_length=100)
    preferred_name: str | None = Field(default=None, max_length=100)
    casual_name: str | None = Field(default=None, max_length=100)
    vocative_name: str | None = Field(default=None, max_length=100)
    age: int | None = Field(default=None, ge=1, le=120)
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=20)
