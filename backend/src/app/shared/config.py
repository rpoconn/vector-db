"""Application configuration loaded from environment variables / `.env`."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BACKEND_DIR / "data"


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
    secret_key: SecretStr = SecretStr("dev-insecure-secret-change-me")
    frontend_url: str = "http://localhost:5173"

    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: SecretStr | None = None

    smtp_host: str | None = None
    smtp_port: int = 1025

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    vector_store_persist_dir: str | None = None

    @property
    def cors_origins(self) -> list[str]:
        return [self.frontend_url]


@lru_cache
def get_settings() -> Settings:
    return Settings()
