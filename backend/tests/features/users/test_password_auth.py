import logging

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.features.users.auth import AUTH_COOKIE_NAME
from app.shared.email import EmailDeliveryError, OutgoingEmail

from .conftest import PASSWORD, Outbox, Register, login


async def test_register_login_and_read_current_user(
    client: AsyncClient, register: Register
) -> None:
    user_id = await register("bob@example.com")

    response = await client.post(
        "/auth/login", data={"username": "bob@example.com", "password": PASSWORD}
    )

    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{AUTH_COOKIE_NAME}=")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" not in cookie  # Plain-HTTP dev/test servers; set in prod.
    me = (await client.get("/users/me")).json()
    assert me == {
        "id": user_id,
        "email": "bob@example.com",
        "is_active": True,
        "is_superuser": False,
        "is_verified": False,
    }


async def test_current_user_requires_login(client: AsyncClient) -> None:
    response = await client.get("/users/me")

    assert response.status_code == 401


async def test_logout_ends_the_session(client: AsyncClient, register: Register) -> None:
    await register("bob@example.com")
    assert await login(client, "bob@example.com") == 204

    response = await client.post("/auth/logout")

    assert response.status_code == 204
    assert (await client.get("/users/me")).status_code == 401


async def test_email_is_unique_regardless_of_case(client: AsyncClient, register: Register) -> None:
    await register("bob@example.com")

    response = await client.post(
        "/auth/register", json={"email": "Bob@Example.COM", "password": PASSWORD}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "REGISTER_USER_ALREADY_EXISTS"


async def test_login_is_case_insensitive_on_email(client: AsyncClient, register: Register) -> None:
    await register("bob@example.com")

    assert await login(client, "BOB@example.com") == 204


@pytest.mark.parametrize(
    ("password", "reason"),
    [
        ("short", "Password must be at least 8 characters"),
        ("xBOB@example.comx", "Password must not contain the e-mail address"),
    ],
)
async def test_register_rejects_weak_passwords(
    client: AsyncClient, password: str, reason: str
) -> None:
    response = await client.post(
        "/auth/register", json={"email": "bob@example.com", "password": password}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == {"code": "REGISTER_INVALID_PASSWORD", "reason": reason}


async def test_login_rejects_wrong_password(client: AsyncClient, register: Register) -> None:
    await register("bob@example.com")

    response = await client.post(
        "/auth/login", data={"username": "bob@example.com", "password": "not-the-password"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "LOGIN_BAD_CREDENTIALS"


async def test_forgot_and_reset_password(
    client: AsyncClient, register: Register, outbox: Outbox
) -> None:
    await register("bob@example.com")

    response = await client.post("/auth/forgot-password", json={"email": "bob@example.com"})

    assert response.status_code == 202
    (message,) = outbox.messages
    assert message.to == "bob@example.com"
    assert "http://localhost:5173/reset-password?token=" in message.body

    response = await client.post(
        "/auth/reset-password",
        json={"token": outbox.token_for("bob@example.com"), "password": "a-brand-new-secret"},
    )

    assert response.status_code == 200
    assert await login(client, "bob@example.com") == 400
    assert await login(client, "bob@example.com", "a-brand-new-secret") == 204


async def test_reset_token_works_only_once(
    client: AsyncClient, register: Register, outbox: Outbox
) -> None:
    await register("bob@example.com")
    await client.post("/auth/forgot-password", json={"email": "bob@example.com"})
    token = outbox.token_for("bob@example.com")
    await client.post("/auth/reset-password", json={"token": token, "password": "first-new-pass"})

    response = await client.post(
        "/auth/reset-password", json={"token": token, "password": "second-new-pass"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "RESET_PASSWORD_BAD_TOKEN"


async def test_reset_password_applies_password_policy(
    client: AsyncClient, register: Register, outbox: Outbox
) -> None:
    await register("bob@example.com")
    await client.post("/auth/forgot-password", json={"email": "bob@example.com"})

    response = await client.post(
        "/auth/reset-password",
        json={"token": outbox.token_for("bob@example.com"), "password": "short"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "RESET_PASSWORD_INVALID_PASSWORD"


async def test_forgot_password_for_unknown_email_reveals_nothing(
    client: AsyncClient, outbox: Outbox
) -> None:
    response = await client.post("/auth/forgot-password", json={"email": "nobody@example.com"})

    assert response.status_code == 202
    assert outbox.messages == []


async def test_forgot_password_survives_email_delivery_failure(
    app: FastAPI,
    client: AsyncClient,
    register: Register,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenSender:
        async def send(self, message: OutgoingEmail) -> None:
            raise EmailDeliveryError("mail server down")

    await register("bob@example.com")
    app.state.email_sender = BrokenSender()
    monkeypatch.setattr(logging.getLogger("app"), "propagate", True)  # Reach caplog's handler.

    with caplog.at_level(logging.ERROR, logger="app"):
        response = await client.post("/auth/forgot-password", json={"email": "bob@example.com"})

    assert response.status_code == 202
    assert "Could not deliver 'Reset your Storefront password'" in caplog.text


async def test_verify_email(client: AsyncClient, register: Register, outbox: Outbox) -> None:
    await register("bob@example.com")

    response = await client.post("/auth/request-verify-token", json={"email": "bob@example.com"})

    assert response.status_code == 202
    assert "http://localhost:5173/verify-email?token=" in outbox.messages[-1].body
    response = await client.post(
        "/auth/verify", json={"token": outbox.token_for("bob@example.com")}
    )
    assert response.status_code == 200
    assert response.json()["is_verified"] is True


async def test_no_oauth_providers_without_credentials(client: AsyncClient) -> None:
    response = await client.get("/auth/providers")

    assert response.json() == []
    assert "/auth/google/authorize" not in (await client.get("/openapi.json")).json()["paths"]


async def test_openapi_documents_auth_routes(client: AsyncClient) -> None:
    paths = (await client.get("/openapi.json")).json()["paths"]

    for path in [
        "/auth/login",
        "/auth/logout",
        "/auth/register",
        "/auth/forgot-password",
        "/auth/reset-password",
        "/auth/verify",
        "/auth/providers",
        "/users/me",
    ]:
        assert path in paths
