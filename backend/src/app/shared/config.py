"""Application configuration loaded from environment variables / `.env`."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BACKEND_DIR / "data"
DEV_SECRET_KEY = "dev-insecure-secret-change-me-before-deploying"
MIN_SECRET_KEY_LENGTH = 32
"""Bytes of key material HMAC-SHA256 (used for session and reset tokens) needs."""


def _default_database_url() -> str:
    return f"sqlite+aiosqlite:///{(DATA_DIR / 'storefront.db').as_posix()}"


class Settings(BaseSettings):
    """Runtime settings. Every field can be overridden with an `APP_`-prefixed env var."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    database_url: str = _default_database_url()
    images_dir: Path = DATA_DIR / "images"
    abo_dir: Path = DATA_DIR / "abo"
    secret_key: SecretStr = SecretStr(DEV_SECRET_KEY)
    frontend_url: str = "http://localhost:5173"
    session_lifetime_seconds: int = 7 * 24 * 3600

    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: SecretStr | None = None

    smtp_host: str | None = None
    smtp_port: int = 1025
    email_from: str = "Storefront <no-reply@storefront.local>"

    embedder: Literal["fastembed", "hashing"] = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_cache_dir: Path = DATA_DIR / "models"
    vector_store: Literal["chroma", "numpy"] = "chroma"
    vector_store_persist_dir: Path | None = None

    @model_validator(mode="after")
    def _require_real_secret_in_prod(self) -> Self:
        secret = self.secret_key.get_secret_value()
        if self.env == "prod" and (
            secret == DEV_SECRET_KEY or len(secret.encode()) < MIN_SECRET_KEY_LENGTH
        ):
            raise ValueError(
                f"APP_SECRET_KEY must be a random string of at least {MIN_SECRET_KEY_LENGTH} "
                "bytes in prod"
            )
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [self.frontend_url]

    @property
    def secure_cookies(self) -> bool:
        """Mark auth cookies `Secure` (HTTPS only) outside local development and tests."""
        return self.env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
