"""Outgoing e-mail: always logged, optionally delivered over SMTP (e.g. a local Mailpit)."""

import email.message
import logging
from typing import Protocol

import aiosmtplib
from fastapi import Request
from pydantic import BaseModel, EmailStr

from app.shared.config import Settings
from app.shared.retry import async_retrying

logger = logging.getLogger(__name__)


class OutgoingEmail(BaseModel):
    to: EmailStr
    subject: str
    body: str


class EmailDeliveryError(Exception):
    """The message could not be handed to the mail server."""


class EmailSender(Protocol):
    async def send(self, message: OutgoingEmail) -> None:
        """Deliver `message`; raises `EmailDeliveryError` when delivery fails."""
        ...


class LoggingEmailSender:
    """Writes messages to the log instead of sending them.

    Bodies (which carry one-time links) are logged only when `include_body` is set.
    """

    def __init__(self, *, include_body: bool = True) -> None:
        self._include_body = include_body

    async def send(self, message: OutgoingEmail) -> None:
        if self._include_body:
            logger.info("E-mail to %s: %s\n%s", message.to, message.subject, message.body)
        else:
            logger.info("E-mail to %s: %s", message.to, message.subject)


def is_transient_smtp_error(exc: BaseException) -> bool:
    """Connection problems and 4xx replies; 5xx replies are permanent."""
    if isinstance(exc, aiosmtplib.SMTPResponseException):
        return 400 <= exc.code < 500
    return isinstance(exc, OSError)  # Connect/disconnect/timeout errors subclass OSError.


class SmtpEmailSender(LoggingEmailSender):
    """Logs every message, then delivers it to an SMTP server (no auth, no TLS)."""

    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        *,
        include_body: bool = True,
        attempts: int = 3,
        retry_min_wait: float = 0.5,
        timeout: float = 10.0,
    ) -> None:
        super().__init__(include_body=include_body)
        self._host = host
        self._port = port
        self._sender = sender
        self._attempts = attempts
        self._retry_min_wait = retry_min_wait
        self._timeout = timeout

    async def send(self, message: OutgoingEmail) -> None:
        await super().send(message)
        mime = email.message.EmailMessage()
        mime["From"] = self._sender
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.body)
        policy = async_retrying(
            is_transient_smtp_error, attempts=self._attempts, min_wait=self._retry_min_wait
        )
        try:
            await policy(
                aiosmtplib.send,
                mime,
                hostname=self._host,
                port=self._port,
                timeout=self._timeout,
            )
        except (aiosmtplib.SMTPException, OSError) as exc:
            server = f"{self._host}:{self._port}"
            raise EmailDeliveryError(f"Could not send e-mail via {server}") from exc
        logger.info("Delivered e-mail to %s via %s:%d", message.to, self._host, self._port)


def create_email_sender(settings: Settings) -> EmailSender:
    include_body = settings.env != "prod"
    if settings.smtp_host is None:
        return LoggingEmailSender(include_body=include_body)
    return SmtpEmailSender(
        settings.smtp_host, settings.smtp_port, settings.email_from, include_body=include_body
    )


def get_email_sender(request: Request) -> EmailSender:
    sender: EmailSender = request.app.state.email_sender
    return sender
