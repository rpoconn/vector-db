"""Session authentication (JWT in an httpOnly cookie) and the configured OAuth providers."""

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi_users.authentication import AuthenticationBackend, CookieTransport, JWTStrategy
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.clients.microsoft import MicrosoftGraphOAuth2
from httpx_oauth.oauth2 import BaseOAuth2
from pydantic import SecretStr

from app.features.users.models import User
from app.shared.config import Settings

AUTH_COOKIE_NAME = "storefront_auth"
OAUTH_CALLBACK_PATH = "/auth/callback"
"""Frontend route the providers redirect back to (`<frontend_url>/auth/callback/<provider>`)."""


def build_auth_backend(settings: Settings) -> AuthenticationBackend[User, uuid.UUID]:
    """Login sets a JWT cookie the SPA never reads; logout clears it."""
    transport = CookieTransport(
        cookie_name=AUTH_COOKIE_NAME,
        cookie_max_age=settings.session_lifetime_seconds,
        cookie_secure=settings.secure_cookies,
        cookie_httponly=True,
        cookie_samesite="lax",
    )
    secret = settings.secret_key.get_secret_value()

    def get_strategy() -> JWTStrategy[User, uuid.UUID]:
        return JWTStrategy(secret=secret, lifetime_seconds=settings.session_lifetime_seconds)

    return AuthenticationBackend(name="cookie", transport=transport, get_strategy=get_strategy)


@dataclass(frozen=True, slots=True)
class OAuthProvider:
    client: BaseOAuth2[Any]
    display_name: str

    @property
    def name(self) -> str:
        return self.client.name

    def redirect_url(self, settings: Settings) -> str:
        return f"{settings.frontend_url.rstrip('/')}{OAUTH_CALLBACK_PATH}/{self.name}"


def _credentials(client_id: str | None, secret: SecretStr | None) -> tuple[str, str] | None:
    """Both halves of a client credential, or None when either is unset or blank."""
    if client_id and secret is not None and secret.get_secret_value():
        return client_id, secret.get_secret_value()
    return None


def build_oauth_providers(settings: Settings) -> list[OAuthProvider]:
    """Providers whose client credentials are configured.

    Apple would slot in here as an `OpenID` client; see the README for what it needs.
    """
    providers: list[OAuthProvider] = []
    if google := _credentials(settings.google_client_id, settings.google_client_secret):
        providers.append(OAuthProvider(GoogleOAuth2(*google), "Google"))
    if microsoft := _credentials(settings.microsoft_client_id, settings.microsoft_client_secret):
        providers.append(OAuthProvider(MicrosoftGraphOAuth2(*microsoft), "Microsoft"))
    return providers
