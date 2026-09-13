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
    stt_provider: str = "openrouter"
    stt_base_url: str = ""
    stt_api_key: str = ""
    stt_model: str = "openai/whisper-large-v3"
    stt_timeout_seconds: int = 90
    tts_provider: str = "openrouter"
    tts_base_url: str = ""
    tts_api_key: str = ""
    tts_model: str = "google/gemini-3.1-flash-tts-preview"
    tts_timeout_seconds: int = 180
    tts_response_format: str = "pcm"
    tts_pcm_sample_rate_hz: int = 24000

    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")


settings = Settings()
