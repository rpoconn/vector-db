import logging
from typing import Any

import aiosmtplib
import pytest

from app.shared.config import Settings
from app.shared.email import (
    EmailDeliveryError,
    LoggingEmailSender,
    OutgoingEmail,
    SmtpEmailSender,
    create_email_sender,
)

MESSAGE = OutgoingEmail(to="bob@example.com", subject="Hi", body="secret link")


@pytest.fixture(autouse=True)
def capture_app_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(logging.getLogger("app"), "propagate", True)


class FakeSmtp:
    """Stands in for `aiosmtplib.send`, failing with each queued error before succeeding."""

    def __init__(self, *errors: Exception) -> None:
        self.errors = list(errors)
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    async def __call__(self, message: Any, **kwargs: Any) -> None:
        self.calls.append((message, kwargs))
        if self.errors:
            raise self.errors.pop(0)


@pytest.fixture
def smtp(monkeypatch: pytest.MonkeyPatch) -> FakeSmtp:
    fake = FakeSmtp()
    monkeypatch.setattr(aiosmtplib, "send", fake)
    return fake


def sender() -> SmtpEmailSender:
    return SmtpEmailSender("mail.test", 1025, "Shop <shop@example.com>", retry_min_wait=0)


@pytest.mark.parametrize("include_body", [True, False])
async def test_logging_sender_logs_body_only_when_allowed(
    caplog: pytest.LogCaptureFixture, include_body: bool
) -> None:
    with caplog.at_level(logging.INFO):
        await LoggingEmailSender(include_body=include_body).send(MESSAGE)

    assert "bob@example.com: Hi" in caplog.text
    assert ("secret link" in caplog.text) is include_body


async def test_smtp_sender_delivers_a_mime_message(smtp: FakeSmtp) -> None:
    await sender().send(MESSAGE)

    ((mime, kwargs),) = smtp.calls
    assert mime["From"] == "Shop <shop@example.com>"
    assert (mime["To"], mime["Subject"]) == (MESSAGE.to, "Hi")
    assert mime.get_content().strip() == "secret link"
    assert (kwargs["hostname"], kwargs["port"]) == ("mail.test", 1025)


async def test_smtp_sender_retries_transient_failures(smtp: FakeSmtp) -> None:
    smtp.errors = [
        aiosmtplib.SMTPConnectError("refused"),
        aiosmtplib.SMTPResponseException(421, "busy"),
    ]

    await sender().send(MESSAGE)

    assert len(smtp.calls) == 3


async def test_smtp_sender_does_not_retry_permanent_failures(smtp: FakeSmtp) -> None:
    smtp.errors = [aiosmtplib.SMTPResponseException(550, "no such mailbox")]

    with pytest.raises(EmailDeliveryError):
        await sender().send(MESSAGE)

    assert len(smtp.calls) == 1


async def test_smtp_sender_gives_up_after_its_attempts(smtp: FakeSmtp) -> None:
    smtp.errors = [aiosmtplib.SMTPServerDisconnected("gone")] * 3

    with pytest.raises(EmailDeliveryError):
        await sender().send(MESSAGE)

    assert len(smtp.calls) == 3


def test_create_email_sender_uses_smtp_only_when_configured() -> None:
    assert type(create_email_sender(Settings(_env_file=None))) is LoggingEmailSender
    smtp = create_email_sender(Settings(smtp_host="localhost", _env_file=None))
    assert isinstance(smtp, SmtpEmailSender)
