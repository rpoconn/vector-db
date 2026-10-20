import uuid
from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.clients.microsoft import MicrosoftGraphOAuth2
from httpx_oauth.oauth2 import BaseOAuth2, OAuth2Token
from pydantic import SecretStr
from sqlalchemy import func, select

from app.features.users.auth import OAUTH_LINK_COOKIE_NAME
from app.features.users.models import OAuthAccount, User
from app.shared.config import Settings
from app.shared.database import Database

from .conftest import Outbox, Register, login

PROVIDERS = ["google", "microsoft"]

type Identities = dict[str, tuple[str, str | None]]


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
def provider_identity(monkeypatch: pytest.MonkeyPatch) -> Identities:
    """Stubs the providers' token exchange; set `[provider] = (account_id, email)` per test."""
    identities: Identities = {}

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


@pytest.fixture
async def other_browser(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """A second client with its own cookie jar."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


async def oauth_login(client: AsyncClient, provider: str) -> Response:
    """Runs authorize -> provider redirect -> callback, as the SPA's callback route does."""
    response = await client.get(f"/auth/{provider}/authorize")
    assert response.status_code == 200
    query = parse_qs(urlsplit(response.json()["authorization_url"]).query)
    return await client.get(
        f"/auth/{provider}/callback", params={"code": "abc", "state": query["state"][0]}
    )


async def confirm(client: AsyncClient, token: str) -> Response:
    return await client.post("/auth/oauth/confirm", json={"token": token})


async def microsoft_login_confirmed(client: AsyncClient, outbox: Outbox, email: str) -> None:
    """Microsoft sign-in including the e-mail confirmation round trip, in one browser."""
    assert (await oauth_login(client, "microsoft")).status_code == 202
    assert (await confirm(client, outbox.token_for(email))).status_code == 204


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


# --- Google: verified addresses, linked immediately ---------------------------------------


async def test_google_login_with_existing_email_signs_in_to_that_account(
    client: AsyncClient, database: Database, register: Register, provider_identity: Identities
) -> None:
    user_id = await register("bob@gmail.com")
    provider_identity["google"] = ("google-123", "BOB@gmail.com")

    assert (await oauth_login(client, "google")).status_code == 204

    assert (await client.get("/users/me")).json()["id"] == user_id
    users, links = await accounts(database)
    assert [str(user.id) for user in users] == [user_id]
    (link,) = links
    assert (link.user_id, link.oauth_name, link.account_id) == (
        uuid.UUID(user_id),
        "google",
        "google-123",
    )


async def test_google_login_with_new_email_creates_a_verified_user(
    client: AsyncClient, database: Database, provider_identity: Identities
) -> None:
    provider_identity["google"] = ("g-1", "alice@gmail.com")

    assert (await oauth_login(client, "google")).status_code == 204

    me = (await client.get("/users/me")).json()
    assert (me["email"], me["is_verified"]) == ("alice@gmail.com", True)
    users, links = await accounts(database)
    assert len(users) == len(links) == 1


# --- Microsoft: unverified addresses, confirmed by e-mail before linking ------------------


async def test_microsoft_login_waits_for_email_confirmation(
    client: AsyncClient,
    database: Database,
    register: Register,
    outbox: Outbox,
    provider_identity: Identities,
) -> None:
    await register("bob@gmail.com")
    provider_identity["microsoft"] = ("ms-123", "BOB@gmail.com")

    response = await oauth_login(client, "microsoft")

    assert response.status_code == 202
    assert response.json() == {"email": "BOB@gmail.com"}
    cookie = next(c for c in response.headers.get_list("set-cookie") if OAUTH_LINK_COOKIE_NAME in c)
    assert "HttpOnly" in cookie
    assert (await client.get("/users/me")).status_code == 401
    _, links = await accounts(database)
    assert links == []
    (message,) = outbox.messages
    assert message.to == "BOB@gmail.com"
    assert "http://localhost:5173/auth/confirm-link?token=" in message.body


async def test_confirmed_microsoft_login_signs_in_to_the_existing_account(
    client: AsyncClient,
    database: Database,
    register: Register,
    outbox: Outbox,
    provider_identity: Identities,
) -> None:
    user_id = await register("bob@gmail.com")
    provider_identity["microsoft"] = ("ms-123", "BOB@gmail.com")
    assert (await oauth_login(client, "microsoft")).status_code == 202

    response = await confirm(client, outbox.token_for("BOB@gmail.com"))

    assert response.status_code == 204
    assert OAUTH_LINK_COOKIE_NAME not in client.cookies
    assert (await client.get("/users/me")).json()["id"] == user_id
    users, links = await accounts(database)
    assert [str(user.id) for user in users] == [user_id]
    (link,) = links
    assert (link.user_id, link.oauth_name, link.account_id) == (
        uuid.UUID(user_id),
        "microsoft",
        "ms-123",
    )


async def test_linked_microsoft_account_signs_in_without_another_email(
    client: AsyncClient, outbox: Outbox, provider_identity: Identities
) -> None:
    provider_identity["microsoft"] = ("ms-123", "bob@gmail.com")
    await microsoft_login_confirmed(client, outbox, "bob@gmail.com")
    await client.post("/auth/logout")

    response = await oauth_login(client, "microsoft")

    assert response.status_code == 204
    assert len(outbox.messages) == 1
    assert (await client.get("/users/me")).json()["email"] == "bob@gmail.com"


async def test_microsoft_login_with_new_email_creates_user_only_after_confirmation(
    client: AsyncClient, database: Database, outbox: Outbox, provider_identity: Identities
) -> None:
    provider_identity["microsoft"] = ("ms-1", "alice@outlook.com")

    assert (await oauth_login(client, "microsoft")).status_code == 202
    assert await accounts(database) == ([], [])

    assert (await confirm(client, outbox.token_for("alice@outlook.com"))).status_code == 204
    me = (await client.get("/users/me")).json()
    assert (me["email"], me["is_verified"]) == ("alice@outlook.com", True)


async def test_victim_clicking_the_link_does_not_link_an_attackers_identity(
    client: AsyncClient,
    other_browser: AsyncClient,
    database: Database,
    register: Register,
    outbox: Outbox,
    provider_identity: Identities,
) -> None:
    """An attacker's tenant names their Microsoft account after the victim's address.

    The confirmation mail reaches the victim; opening it in the victim's own browser (which
    lacks the attacker's link cookie) must not attach the attacker's identity.
    """
    victim_id = await register("victim@gmail.com")
    provider_identity["microsoft"] = ("attacker-ms", "victim@gmail.com")
    attacker = client
    assert (await oauth_login(attacker, "microsoft")).status_code == 202

    victim = other_browser
    assert await login(victim, "victim@gmail.com") == 204
    response = await confirm(victim, outbox.token_for("victim@gmail.com"))

    assert response.status_code == 400
    assert response.json()["detail"] == "OAUTH_LINK_BAD_TOKEN"
    _, links = await accounts(database)
    assert links == []
    assert (await attacker.get("/users/me")).status_code == 401
    assert (await victim.get("/users/me")).json()["id"] == victim_id


async def test_confirmation_requires_the_token_not_just_the_cookie(
    client: AsyncClient, outbox: Outbox, provider_identity: Identities
) -> None:
    provider_identity["microsoft"] = ("ms-1", "bob@gmail.com")
    await oauth_login(client, "microsoft")
    token = outbox.token_for("bob@gmail.com")
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")

    for bad in ["not-a-token", tampered]:
        response = await confirm(client, bad)

        assert response.status_code == 400
        assert response.json()["detail"] == "OAUTH_LINK_BAD_TOKEN"


async def test_one_account_can_link_both_providers_and_keep_its_password(
    client: AsyncClient,
    database: Database,
    register: Register,
    outbox: Outbox,
    provider_identity: Identities,
) -> None:
    user_id = await register("bob@gmail.com")
    provider_identity["google"] = ("g-1", "bob@gmail.com")
    provider_identity["microsoft"] = ("m-1", "bob@gmail.com")

    assert (await oauth_login(client, "google")).status_code == 204
    await microsoft_login_confirmed(client, outbox, "bob@gmail.com")
    assert (await oauth_login(client, "google")).status_code == 204

    users, links = await accounts(database)
    assert [str(user.id) for user in users] == [user_id]
    assert sorted(link.oauth_name for link in links) == PROVIDERS
    assert await login(client, "bob@gmail.com") == 204


# --- Unverified password accounts are claimed by the proven address owner ---------------


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_oauth_owner_claims_an_unverified_account_and_voids_its_password(
    client: AsyncClient,
    register: Register,
    outbox: Outbox,
    provider_identity: Identities,
    provider: str,
) -> None:
    """Someone pre-registered the victim's address with a password they know.

    They can't log in with it (unverified), and once the real owner signs in with a provider,
    the account becomes verified and that password stops working for good.
    """
    victim_id = await register("victim@gmail.com", password="squatter-password", verify=False)
    provider_identity[provider] = (f"{provider}-1", "victim@gmail.com")
    assert await login(client, "victim@gmail.com", "squatter-password") == 400

    if provider == "microsoft":
        await microsoft_login_confirmed(client, outbox, "victim@gmail.com")
    else:
        assert (await oauth_login(client, provider)).status_code == 204

    me = (await client.get("/users/me")).json()
    assert (me["id"], me["is_verified"]) == (victim_id, True)
    await client.post("/auth/logout")
    response = await client.post(
        "/auth/login", data={"username": "victim@gmail.com", "password": "squatter-password"}
    )
    assert response.json()["detail"] == "LOGIN_BAD_CREDENTIALS"


async def test_unconfirmed_microsoft_login_leaves_an_unverified_account_untouched(
    client: AsyncClient,
    database: Database,
    register: Register,
    provider_identity: Identities,
) -> None:
    await register("bob@gmail.com", verify=False)
    provider_identity["microsoft"] = ("ms-1", "bob@gmail.com")

    assert (await oauth_login(client, "microsoft")).status_code == 202

    (user,), _ = await accounts(database)
    assert not user.is_verified


# --- Shared failure modes --------------------------------------------------------------


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_oauth_without_email_is_rejected(
    client: AsyncClient, database: Database, provider_identity: Identities, provider: str
) -> None:
    provider_identity[provider] = ("id-1", None)

    assert (await oauth_login(client, provider)).status_code == 400

    async with database.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == 0


async def test_oauth_callback_rejects_forged_state(
    client: AsyncClient, provider_identity: Identities
) -> None:
    provider_identity["google"] = ("g-1", "bob@gmail.com")

    response = await client.get("/auth/google/callback", params={"code": "abc", "state": "x"})

    assert response.status_code == 400
    assert (await client.get("/users/me")).status_code == 401


async def test_openapi_documents_the_confirmation_step(client: AsyncClient) -> None:
    spec = (await client.get("/openapi.json")).json()
    paths = spec["paths"]

    assert "202" in paths["/auth/microsoft/callback"]["get"]["responses"]
    assert "202" not in paths["/auth/google/callback"]["get"]["responses"]
    assert "202" not in paths["/auth/microsoft/authorize"]["get"]["responses"]
    assert "/auth/oauth/confirm" in paths
    assert "OAuthEmailConfirmationSent" in spec["components"]["schemas"]
