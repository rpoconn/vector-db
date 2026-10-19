"""Account lifecycle hooks: password policy and the e-mails sent for reset and verification."""

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Annotated
from urllib.parse import urlencode

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, InvalidPasswordException, UUIDIDMixin, schemas
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import OAuthAccount, User
from app.shared.config import Settings
from app.shared.database import get_session
from app.shared.email import EmailDeliveryError, EmailSender, OutgoingEmail, get_email_sender

logger = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 8
RESET_PASSWORD_PATH = "/reset-password"
VERIFY_EMAIL_PATH = "/verify-email"


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    def __init__(
        self,
        user_db: SQLAlchemyUserDatabase[User, uuid.UUID],
        settings: Settings,
        email_sender: EmailSender,
    ) -> None:
        super().__init__(user_db)
        secret = settings.secret_key.get_secret_value()
        self.reset_password_token_secret = secret
        self.verification_token_secret = secret
        self._frontend_url = settings.frontend_url.rstrip("/")
        self._email_sender = email_sender

    async def validate_password(self, password: str, user: schemas.BaseUserCreate | User) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise InvalidPasswordException(
                reason=f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
            )
        if user.email.lower() in password.lower():
            raise InvalidPasswordException(reason="Password must not contain the e-mail address")

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        logger.info("Registered user %s", user.id)

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        link = self._frontend_link(RESET_PASSWORD_PATH, token)
        await self._send(
            OutgoingEmail(
                to=user.email,
                subject="Reset your Storefront password",
                body=(
                    "Someone asked to reset the password for this account.\n\n"
                    f"Choose a new password: {link}\n\n"
                    "If it wasn't you, ignore this e-mail; your password stays the same."
                ),
            )
        )

    async def on_after_reset_password(self, user: User, request: Request | None = None) -> None:
        logger.info("User %s reset their password", user.id)

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        link = self._frontend_link(VERIFY_EMAIL_PATH, token)
        await self._send(
            OutgoingEmail(
                to=user.email,
                subject="Confirm your Storefront e-mail address",
                body=f"Confirm this address: {link}",
            )
        )

    def _frontend_link(self, path: str, token: str) -> str:
        return f"{self._frontend_url}{path}?{urlencode({'token': token})}"

    async def _send(self, message: OutgoingEmail) -> None:
        # Never fail the request: the endpoints must not reveal whether an account exists.
        try:
            await self._email_sender.send(message)
        except EmailDeliveryError:
            logger.exception("Could not deliver %r", message.subject)


async def get_user_db(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AsyncIterator[SQLAlchemyUserDatabase[User, uuid.UUID]]:
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


async def get_user_manager(
    request: Request,
    user_db: Annotated[SQLAlchemyUserDatabase[User, uuid.UUID], Depends(get_user_db)],
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> AsyncIterator[UserManager]:
    settings: Settings = request.app.state.settings
    yield UserManager(user_db, settings, email_sender)
