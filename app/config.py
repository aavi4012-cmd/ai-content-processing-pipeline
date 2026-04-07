from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """
    Centralized configuration loaded from environment variables or .env file.
    All sensitive values (API keys, DB credentials) are injected via env vars.
    """

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://postgres:postgres@db:5432/ai_pipeline"

    # ── Redis & Celery ────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"

    # ── LLM Provider ─────────────────────────────────────────
    OPENAI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT: int = 30  # seconds — protects against LLM hangs

    # ── Retry Logic ──────────────────────────────────────────
    MAX_RETRIES: int = 3
    RETRY_BACKOFF: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
