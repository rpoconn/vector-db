import pytest
from pydantic import SecretStr, ValidationError

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


@pytest.mark.parametrize("secret", [None, "too-short"])
def test_prod_requires_a_real_secret_key(secret: str | None) -> None:
    overrides = {} if secret is None else {"secret_key": SecretStr(secret)}

    with pytest.raises(ValidationError, match="APP_SECRET_KEY"):
        Settings(env="prod", _env_file=None, **overrides)  # type: ignore[arg-type]


def test_cookies_are_secure_only_in_prod() -> None:
    prod = Settings(env="prod", secret_key=SecretStr("x" * 32), _env_file=None)

    assert prod.secure_cookies
    assert not Settings(env="dev", _env_file=None).secure_cookies
