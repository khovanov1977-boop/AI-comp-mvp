from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://ai_companion:ai_companion@localhost:5432/ai_companion"
    frontend_origin: str = "http://localhost:3000"
    llm_provider: str = "mock"

    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")


settings = Settings()
