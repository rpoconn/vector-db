"""OpenAPI spec export for the frontend's generated, typed API client."""

from typing import Any

from pydantic import SecretStr

from app.main import create_app
from app.shared.config import Settings

_PLACEHOLDER_CLIENT_ID = "openapi-export"
_PLACEHOLDER_SECRET = SecretStr("openapi-export")


def build_openapi_spec() -> dict[str, Any]:
    """The API spec with every optional router mounted, independent of the local `.env`.

    OAuth routes only exist when a provider is configured, so placeholder credentials enable
    them all; the app is never started, so nothing contacts the providers.
    """
    settings = Settings(
        google_client_id=_PLACEHOLDER_CLIENT_ID,
        google_client_secret=_PLACEHOLDER_SECRET,
        microsoft_client_id=_PLACEHOLDER_CLIENT_ID,
        microsoft_client_secret=_PLACEHOLDER_SECRET,
        _env_file=None,
    )
    return create_app(settings).openapi()
