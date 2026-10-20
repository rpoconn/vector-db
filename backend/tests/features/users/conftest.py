import re
from collections.abc import Awaitable, Callable

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.shared.email import OutgoingEmail

PASSWORD = "correct-horse-battery"

type Register = Callable[..., Awaitable[str]]


class Outbox:
    """EmailSender test double that keeps every message."""

    def __init__(self) -> None:
        self.messages: list[OutgoingEmail] = []

    async def send(self, message: OutgoingEmail) -> None:
        self.messages.append(message)

    def token_for(self, to: str) -> str:
        """The `token` query parameter of the last link e-mailed to `to`."""
        message = next(m for m in reversed(self.messages) if m.to == to)
        match = re.search(r"\?token=([\w.-]+)", message.body)
        assert match is not None, message.body
        return match.group(1)


@pytest.fixture
def outbox(app: FastAPI) -> Outbox:
    box = Outbox()
    app.state.email_sender = box
    return box


@pytest.fixture
def register(client: AsyncClient, outbox: Outbox) -> Register:
    """Registers a password account, verified via its e-mail unless `verify=False`; returns its id.

    Leaves the outbox empty so tests only see the messages they cause.
    """

    async def run(email: str, password: str = PASSWORD, *, verify: bool = True) -> str:
        response = await client.post("/auth/register", json={"email": email, "password": password})
        assert response.status_code == 201, response.text
        if verify:
            verified = await client.post("/auth/verify", json={"token": outbox.token_for(email)})
            assert verified.status_code == 200, verified.text
        outbox.messages.clear()
        user_id: str = response.json()["id"]
        return user_id

    return run


async def login(client: AsyncClient, email: str, password: str = PASSWORD) -> int:
    """Logs in (keeping the session cookie on success); returns the status code."""
    response = await client.post("/auth/login", data={"username": email, "password": password})
    return response.status_code
