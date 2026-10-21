from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.features.mailbox.router import MAILBOX_PATH
from app.main import create_app
from app.shared.config import Settings
from app.shared.email import OutgoingEmail, RecordingEmailSender


async def test_lists_recorded_messages_filtered_by_recipient(
    app: FastAPI, client: AsyncClient
) -> None:
    sender = app.state.email_sender
    assert isinstance(sender, RecordingEmailSender)
    await sender.send(OutgoingEmail(to="bob@example.com", subject="One", body="first"))
    await sender.send(OutgoingEmail(to="alice@example.com", subject="Two", body="second"))
    await sender.send(OutgoingEmail(to="bob@example.com", subject="Three", body="third"))

    everything = await client.get(MAILBOX_PATH)
    assert [m["subject"] for m in everything.json()] == ["One", "Two", "Three"]

    bobs = await client.get(MAILBOX_PATH, params={"to": "BOB@example.com"})
    assert bobs.status_code == 200
    assert [m["body"] for m in bobs.json()] == ["first", "third"]

    assert (await client.delete(MAILBOX_PATH)).status_code == 204
    assert (await client.get(MAILBOX_PATH)).json() == []


async def test_mailbox_is_absent_outside_the_test_environment(tmp_path: Path) -> None:
    settings = Settings(
        env="dev",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'dev.db').as_posix()}",
        images_dir=tmp_path / "images",
        embedder="hashing",
        vector_store="numpy",
        _env_file=None,
    )
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        assert (await client.get(MAILBOX_PATH)).status_code == 404
    assert MAILBOX_PATH not in app.openapi()["paths"]


async def test_mailbox_refuses_when_the_sender_does_not_record(
    app: FastAPI, client: AsyncClient
) -> None:
    app.state.email_sender = object()

    assert (await client.get(MAILBOX_PATH)).status_code == 503
