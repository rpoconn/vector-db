"""Account lifecycle: password policy, e-mail verification, OAuth linking, and their e-mails.

The e-mail address is the account identity, so every way in proves it: password login needs
a verified address, Google sign-ins carry one, and other providers' addresses are confirmed by
an e-mailed link before they can link to or create an account.
"""

import hashlib
import logging
import secrets
import uuid
from collections.abc import AsyncIterator, Callable, Collection
from typing import Annotated
from urllib.parse import urlencode

import jwt
from fastapi import Depends, Request
from fastapi_users import (
    BaseUserManager,
    InvalidPasswordException,
    UUIDIDMixin,
    exceptions,
    schemas,
)
from fastapi_users.jwt import decode_jwt, generate_jwt
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
CONFIRM_OAUTH_LINK_PATH = "/auth/confirm-link"
OAUTH_LINK_TOKEN_AUDIENCE = "storefront:oauth-link"
OAUTH_LINK_LIFETIME_SECONDS = 3600


class OAuthEmailConfirmationRequired(Exception):
    """A provider identity was not linked yet: a confirmation link went to its e-mail.

    `nonce` must be stored in the browser that started the sign-in (see the router); the
    link only works when presented together with it.
    """

    def __init__(self, provider: str, email: str, nonce: str) -> None:
        super().__init__(f"Confirmation of {email} required to link a {provider} account")
        self.provider = provider
        self.email = email
        self.nonce = nonce


class InvalidOAuthLinkToken(Exception):
    """The confirmation link is forged, expired, or opened in a different browser."""


def _nonce_hash(nonce: str) -> str:
    return hashlib.sha256(nonce.encode()).hexdigest()


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    def __init__(
        self,
        user_db: SQLAlchemyUserDatabase[User, uuid.UUID],
        settings: Settings,
        email_sender: EmailSender,
        *,
        confirm_email_for: Collection[str] = (),
    ) -> None:
        """`confirm_email_for`: OAuth providers whose e-mail addresses are not proven to belong
        to the account holder, so we prove ownership ourselves before linking."""
        super().__init__(user_db)
        self._secret = settings.secret_key.get_secret_value()
        self.reset_password_token_secret = self._secret
        self.verification_token_secret = self._secret
        self._frontend_url = settings.frontend_url.rstrip("/")
        self._email_sender = email_sender
        self._confirm_email_for = frozenset(confirm_email_for)

    async def validate_password(self, password: str, user: schemas.BaseUserCreate | User) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise InvalidPasswordException(
                reason=f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
            )
        if user.email.lower() in password.lower():
            raise InvalidPasswordException(reason="Password must not contain the e-mail address")

    async def oauth_callback(
        self,
        oauth_name: str,
        access_token: str,
        account_id: str,
        account_email: str,
        expires_at: int | None = None,
        refresh_token: str | None = None,
        request: Request | None = None,
        *,
        associate_by_email: bool = False,
        is_verified_by_default: bool = False,
    ) -> User:
        """Sign in with a provider identity, linking or creating the account by e-mail.

        For providers in `confirm_email_for`, an identity that is not linked yet is neither
        linked to an existing account nor used to create one until its holder proves they
        receive mail at that address: raises `OAuthEmailConfirmationRequired` instead.
        """
        if oauth_name in self._confirm_email_for:
            try:
                await self.get_by_oauth_account(oauth_name, account_id)
            except exceptions.UserNotExists:
                raise await self._request_link_confirmation(
                    oauth_name, account_id, account_email
                ) from None
        user = await super().oauth_callback(
            oauth_name,
            access_token,
            account_id,
            account_email,
            expires_at,
            refresh_token,
            request,
            associate_by_email=associate_by_email,
            is_verified_by_default=is_verified_by_default,
        )
        return await self._claim_unverified(user)

    async def confirm_oauth_link(
        self, token: str, nonce: str | None, request: Request | None = None
    ) -> User:
        """Finish a sign-in paused by `OAuthEmailConfirmationRequired`; the e-mail is now proven."""
        try:
            data = decode_jwt(token, self._secret, [OAUTH_LINK_TOKEN_AUDIENCE])
            provider, account_id, email = data["provider"], data["account_id"], data["email"]
            expected_nonce_hash = data["nonce_hash"]
        except (jwt.PyJWTError, KeyError) as exc:
            raise InvalidOAuthLinkToken() from exc
        if nonce is None or not secrets.compare_digest(_nonce_hash(nonce), expected_nonce_hash):
            raise InvalidOAuthLinkToken()
        # The provider's access token is not kept across the e-mail round trip; nothing uses it.
        user = await super().oauth_callback(
            provider,
            "",
            account_id,
            email,
            request=request,
            associate_by_email=True,
            is_verified_by_default=True,
        )
        return await self._claim_unverified(user)

    async def _claim_unverified(self, user: User) -> User:
        """The address owner just proved themselves via a provider: hand them the account.

        An unverified account's password was set by someone who never proved they own the
        address (password login refuses it), so it is discarded rather than left for that
        person to use once the account is verified. Verified accounts keep their password.
        """
        if user.is_verified:
            return user
        logger.info("User %s claimed by its e-mail owner via OAuth; password discarded", user.id)
        unusable_password = self.password_helper.hash(self.password_helper.generate())
        return await self.user_db.update(
            user, {"is_verified": True, "hashed_password": unusable_password}
        )

    async def _request_link_confirmation(
        self, provider: str, account_id: str, email: str
    ) -> OAuthEmailConfirmationRequired:
        nonce = secrets.token_urlsafe(32)
        token = generate_jwt(
            {
                "provider": provider,
                "account_id": account_id,
                "email": email,
                "nonce_hash": _nonce_hash(nonce),
                "aud": OAUTH_LINK_TOKEN_AUDIENCE,
            },
            self._secret,
            OAUTH_LINK_LIFETIME_SECONDS,
        )
        link = self._frontend_link(CONFIRM_OAUTH_LINK_PATH, token)
        await self._send(
            OutgoingEmail(
                to=email,
                subject="Confirm your e-mail to finish signing in",
                body=(
                    f"Someone is signing in to Storefront with a {provider.title()} account that "
                    "uses this e-mail address.\n\n"
                    "If it's you, open this link in the same browser within an hour to finish "
                    f"signing in: {link}\n\n"
                    "If it wasn't you, ignore this e-mail; nothing has been linked."
                ),
            )
        )
        logger.info("Sent %s link confirmation for account %s", provider, account_id)
        return OAuthEmailConfirmationRequired(provider, email, nonce)

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        logger.info("Registered user %s", user.id)
        if not user.is_verified:  # Password sign-ups; OAuth sign-ups arrive verified.
            await self.request_verify(user, request)

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
        if not user.is_verified:  # The reset link was e-mailed, so the address is proven.
            await self.user_db.update(user, {"is_verified": True})

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


type UserManagerDependency = Callable[..., AsyncIterator[UserManager]]


def user_manager_dependency(
    settings: Settings, *, confirm_email_for: Collection[str] = ()
) -> UserManagerDependency:
    """FastAPI dependency building a `UserManager` per request."""

    async def get_user_manager(
        user_db: Annotated[SQLAlchemyUserDatabase[User, uuid.UUID], Depends(get_user_db)],
        email_sender: Annotated[EmailSender, Depends(get_email_sender)],
    ) -> AsyncIterator[UserManager]:
        yield UserManager(user_db, settings, email_sender, confirm_email_for=confirm_email_for)

    return get_user_manager
