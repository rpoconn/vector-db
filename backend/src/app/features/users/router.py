"""Auth and account routes: password login/registration/reset, verification, OAuth, `/users/me`."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import Strategy
from fastapi_users.router.common import ErrorCode, ErrorModel

from app.features.users.auth import (
    OAUTH_LINK_COOKIE_NAME,
    build_auth_backend,
    build_oauth_providers,
)
from app.features.users.manager import (
    OAUTH_LINK_LIFETIME_SECONDS,
    InvalidOAuthLinkToken,
    OAuthEmailConfirmationRequired,
    UserManager,
    user_manager_dependency,
)
from app.features.users.models import User
from app.features.users.schemas import (
    OAuthEmailConfirmationSent,
    OAuthLinkConfirm,
    OAuthProviderOut,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.shared.config import Settings

OAUTH_LINK_BAD_TOKEN = "OAUTH_LINK_BAD_TOKEN"

type ExceptionHandler = Callable[[Request, Exception], Awaitable[Response]]

_CONFIRMATION_SENT_RESPONSE = {
    "model": OAuthEmailConfirmationSent,
    "description": (
        "First sign-in with a provider that does not verify e-mail addresses: a confirmation "
        "link was e-mailed and must be opened in this browser (`POST /auth/oauth/confirm`)."
    ),
}


def install_users(app: FastAPI, settings: Settings) -> None:
    app.include_router(create_users_router(settings))
    app.add_exception_handler(OAuthEmailConfirmationRequired, _confirmation_sent_handler(settings))


def create_users_router(settings: Settings) -> APIRouter:
    backend = build_auth_backend(settings)
    providers = build_oauth_providers(settings)
    get_user_manager = user_manager_dependency(
        settings,
        confirm_email_for=[provider.name for provider in providers if not provider.verifies_email],
    )
    fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [backend])

    router = APIRouter()
    auth_routers = [
        fastapi_users.get_auth_router(backend, requires_verification=True),
        fastapi_users.get_register_router(UserRead, UserCreate),
        fastapi_users.get_reset_password_router(),
        fastapi_users.get_verify_router(UserRead),
    ]
    for auth_router in auth_routers:
        router.include_router(auth_router, prefix="/auth", tags=["auth"])
    router.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"]
    )

    for provider in providers:
        oauth_router = fastapi_users.get_oauth_router(
            provider.client,
            backend,
            settings.secret_key.get_secret_value(),
            redirect_url=provider.redirect_url(settings),
            # The e-mail address is the account identity: a provider login with the address of
            # an existing account signs in to that account. Unverified provider addresses are
            # confirmed by e-mail first (see UserManager.oauth_callback).
            associate_by_email=True,
            is_verified_by_default=True,
            csrf_token_cookie_secure=settings.secure_cookies,
        )
        if not provider.verifies_email:
            for route in oauth_router.routes:
                if isinstance(route, APIRoute) and route.path == "/callback":
                    route.responses[status.HTTP_202_ACCEPTED] = _CONFIRMATION_SENT_RESPONSE
        router.include_router(oauth_router, prefix=f"/auth/{provider.name}", tags=["auth"])

    provider_list = [
        OAuthProviderOut(name=provider.name, display_name=provider.display_name)
        for provider in providers
    ]

    @router.get("/auth/providers", response_model=list[OAuthProviderOut], tags=["auth"])
    async def list_oauth_providers() -> list[OAuthProviderOut]:
        """OAuth providers enabled on this server, for rendering sign-in buttons."""
        return provider_list

    @router.post(
        "/auth/oauth/confirm",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
        tags=["auth"],
        responses={
            status.HTTP_400_BAD_REQUEST: {
                "model": ErrorModel,
                "description": "Link forged, expired, or opened in a different browser.",
            }
        },
    )
    async def confirm_oauth_link(
        body: OAuthLinkConfirm,
        request: Request,
        user_manager: Annotated[UserManager, Depends(get_user_manager)],
        strategy: Annotated[Strategy[User, uuid.UUID], Depends(backend.get_strategy)],
    ) -> Response:
        """Finish a provider sign-in after its e-mail confirmation link was opened."""
        try:
            user = await user_manager.confirm_oauth_link(
                body.token, request.cookies.get(OAUTH_LINK_COOKIE_NAME), request
            )
        except InvalidOAuthLinkToken as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, OAUTH_LINK_BAD_TOKEN) from exc
        if not user.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, ErrorCode.LOGIN_BAD_CREDENTIALS)
        response = await backend.login(strategy, user)
        response.delete_cookie(OAUTH_LINK_COOKIE_NAME)
        await user_manager.on_after_login(user, request, response)
        return response

    return router


def _confirmation_sent_handler(settings: Settings) -> ExceptionHandler:
    async def handle(request: Request, exc: Exception) -> Response:
        assert isinstance(exc, OAuthEmailConfirmationRequired)
        body = OAuthEmailConfirmationSent(email=exc.email)
        response = JSONResponse(body.model_dump(), status_code=status.HTTP_202_ACCEPTED)
        response.set_cookie(
            OAUTH_LINK_COOKIE_NAME,
            exc.nonce,
            max_age=OAUTH_LINK_LIFETIME_SECONDS,
            secure=settings.secure_cookies,
            httponly=True,
            samesite="lax",
        )
        return response

    return handle
