import pytest
from pydantic import SecretStr

from app.shared.config import Settings


def test_env_vars_use_app_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_FRONTEND_URL", "http://example.test:3000")
    monkeypatch.setenv("APP_SMTP_HOST", "mailpit")

    settings = Settings(_env_file=None)

    assert settings.frontend_url == "http://example.test:3000"
    assert settings.cors_origins == ["http://example.test:3000"]
    assert settings.smtp_host == "mailpit"
    assert settings.vector_store_persist_dir is None


def test_secret_key_is_not_exposed_in_repr() -> None:
    settings = Settings(secret_key=SecretStr("super-secret"), _env_file=None)

    assert "super-secret" not in repr(settings)
    assert settings.secret_key.get_secret_value() == "super-secret"
