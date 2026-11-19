from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET = "dev-secret-key-change-me-please-32chars"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Procurement Intelligence Platform"
    app_version: str = "2.0.0"
    environment: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://procurement:procurement@localhost:5432/procurement"

    cors_origins: str = "http://localhost:5173"

    redis_url: str | None = None
    cache_ttl_seconds: int = 300

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5-5"

    qdrant_url: str | None = None
    qdrant_collection: str = "procurement_knowledge"
    embedding_backend: str = "hashing"  # "hashing" (no downloads) or "fastembed" (semantic)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    rag_min_score: float = 0.12  # tuned for the hashing embedder; raise for fastembed

    secret_key: str = _DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Optional: create the first admin automatically on startup when no users exist.
    admin_email: str | None = None
    admin_password: str | None = None

    @model_validator(mode="after")
    def _require_real_secret_in_production(self) -> "Settings":
        if self.environment == "production" and (
            self.secret_key == _DEFAULT_SECRET or len(self.secret_key) < 32
        ):
            raise ValueError("SECRET_KEY must be set to a random value (>= 32 chars) in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
