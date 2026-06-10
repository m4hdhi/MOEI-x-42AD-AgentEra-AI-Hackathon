from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "dev"
    app_log_level: str = "info"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    primary_llm: str = "groq:llama-3.3-70b-versatile"
    arabic_llm: str = "hf:inception/jais-family-30b-chat"
    longctx_llm: str = "google:gemini-2.5-flash"

    groq_api_key: str | None = None
    google_api_key: str | None = None
    openrouter_api_key: str | None = None

    database_url: str = "postgresql+psycopg://hassan:hassan_dev@localhost:5432/hassan"
    redis_url: str = "redis://localhost:6379/0"

    langfuse_host: str = "http://localhost:3001"
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None

    # Comma-separated extra CORS origins (e.g. your ngrok URL)
    cors_extra_origins: str = ""

    @property
    def allowed_origins(self) -> list[str]:
        base = ["http://localhost:3000", "http://localhost:8000"]
        extras = [o.strip() for o in self.cors_extra_origins.split(",") if o.strip()]
        return base + extras


@lru_cache
def get_settings() -> Settings:
    return Settings()
