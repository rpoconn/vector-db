import uuid
from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import AsyncClient
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.clients.microsoft import MicrosoftGraphOAuth2
from httpx_oauth.oauth2 import BaseOAuth2, OAuth2Token
from pydantic import SecretStr
from sqlalchemy import func, select

from app.features.users.models import OAuthAccount, User
from app.shared.config import Settings
from app.shared.database import Database

from .conftest import Register, login

PROVIDERS = ["google", "microsoft"]


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "google_client_id": "google-id",
            "google_client_secret": SecretStr("google-secret"),
            "microsoft_client_id": "microsoft-id",
            "microsoft_client_secret": SecretStr("microsoft-secret"),
        }
    )


@pytest.fixture
def provider_identity(monkeypatch: pytest.MonkeyPatch) -> dict[str, tuple[str, str | None]]:
    """Stubs the providers' token exchange; set `[provider] = (account_id, email)` per test."""
    identities: dict[str, tuple[str, str | None]] = {}

    async def get_access_token(
        self: BaseOAuth2[object], code: str, redirect_uri: str, code_verifier: str | None = None
    ) -> OAuth2Token:
        assert redirect_uri == f"http://localhost:5173/auth/callback/{self.name}"
        return OAuth2Token({"access_token": f"{self.name}-token-{code}", "expires_in": 3600})

    def get_id_email(name: str) -> object:
        async def stub(self: BaseOAuth2[object], token: str) -> tuple[str, str | None]:
            assert token.startswith(f"{name}-token-")
            return identities[name]

        return stub

    monkeypatch.setattr(BaseOAuth2, "get_access_token", get_access_token)
    monkeypatch.setattr(GoogleOAuth2, "get_id_email", get_id_email("google"))
    monkeypatch.setattr(MicrosoftGraphOAuth2, "get_id_email", get_id_email("microsoft"))
    return identities


async def oauth_login(client: AsyncClient, provider: str) -> int:
    """Runs authorize -> provider redirect -> callback, as the SPA's callback route does."""
    response = await client.get(f"/auth/{provider}/authorize")
    assert response.status_code == 200
    query = parse_qs(urlsplit(response.json()["authorization_url"]).query)
    callback = await client.get(
        f"/auth/{provider}/callback", params={"code": "abc", "state": query["state"][0]}
    )
    return callback.status_code


async def accounts(database: Database) -> tuple[list[User], list[OAuthAccount]]:
    async with database.session_factory() as session:
        users = (await session.scalars(select(User))).unique().all()
        links = (await session.scalars(select(OAuthAccount))).all()
    return list(users), list(links)


async def test_providers_are_listed_when_configured(client: AsyncClient) -> None:
    response = await client.get("/auth/providers")

    assert response.json() == [
        {"name": "google", "display_name": "Google"},
        {"name": "microsoft", "display_name": "Microsoft"},
    ]


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_authorize_redirects_back_to_the_frontend(client: AsyncClient, provider: str) -> None:
    response = await client.get(f"/auth/{provider}/authorize")

    query = parse_qs(urlsplit(response.json()["authorization_url"]).query)
    assert query["redirect_uri"] == [f"http://localhost:5173/auth/callback/{provider}"]
    assert "fastapiusersoauthcsrf=" in response.headers["set-cookie"]


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_oauth_login_with_existing_email_signs_in_to_that_account(
    client: AsyncClient,
    database: Database,
    register: Register,
    provider_identity: dict[str, tuple[str, str | None]],
    provider: str,
) -> None:
    user_id = await register("bob@gmail.com")
    provider_identity[provider] = (f"{provider}-123", "Bob@Gmail.com")

    assert await oauth_login(client, provider) == 204

    assert (await client.get("/users/me")).json()["id"] == user_id
    users, links = await accounts(database)
    assert [str(user.id) for user in users] == [user_id]
    (link,) = links
    assert (link.user_id, link.oauth_name, link.account_id) == (
        uuid.UUID(user_id),
        provider,
        f"{provider}-123",
    )


async def test_one_account_can_link_both_providers_and_keep_its_password(
    client: AsyncClient,
    database: Database,
    register: Register,
    provider_identity: dict[str, tuple[str, str | None]],
) -> None:
    user_id = await register("bob@gmail.com")
    provider_identity["google"] = ("g-1", "bob@gmail.com")
    provider_identity["microsoft"] = ("m-1", "bob@gmail.com")

    assert await oauth_login(client, "google") == 204
    assert await oauth_login(client, "microsoft") == 204
    assert await oauth_login(client, "google") == 204

    users, links = await accounts(database)
    assert [str(user.id) for user in users] == [user_id]
    assert sorted(link.oauth_name for link in links) == PROVIDERS
    assert await login(client, "bob@gmail.com") == 204


async def test_oauth_login_with_new_email_creates_a_verified_user(
    client: AsyncClient,
    database: Database,
    provider_identity: dict[str, tuple[str, str | None]],
) -> None:
    provider_identity["google"] = ("g-1", "alice@gmail.com")

    assert await oauth_login(client, "google") == 204

    me = (await client.get("/users/me")).json()
    assert (me["email"], me["is_verified"]) == ("alice@gmail.com", True)
    users, links = await accounts(database)
    assert len(users) == len(links) == 1


async def test_oauth_without_email_is_rejected(
    client: AsyncClient,
    database: Database,
    provider_identity: dict[str, tuple[str, str | None]],
) -> None:
    provider_identity["google"] = ("g-1", None)

    assert await oauth_login(client, "google") == 400

    async with database.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == 0


async def test_oauth_callback_rejects_forged_state(
    client: AsyncClient, provider_identity: dict[str, tuple[str, str | None]]
) -> None:
    provider_identity["google"] = ("g-1", "bob@gmail.com")

    response = await client.get("/auth/google/callback", params={"code": "abc", "state": "x"})

    assert response.status_code == 400
    assert (await client.get("/users/me")).status_code == 401
