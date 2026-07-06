from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://ai_companion:ai_companion@localhost:5432/ai_companion"
    frontend_origin: str = "http://localhost:3000"
    llm_provider: str = "mock"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: int = 60
    llm_temperature: float = 0.8
    llm_max_tokens: int = 500

    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")


settings = Settings()
