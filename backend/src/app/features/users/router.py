"""Auth and account routes: password login/registration/reset, verification, OAuth, `/users/me`."""

import uuid

from fastapi import APIRouter
from fastapi_users import FastAPIUsers

from app.features.users.auth import build_auth_backend, build_oauth_providers
from app.features.users.manager import get_user_manager
from app.features.users.models import User
from app.features.users.schemas import OAuthProviderOut, UserCreate, UserRead, UserUpdate
from app.shared.config import Settings


def create_users_router(settings: Settings) -> APIRouter:
    backend = build_auth_backend(settings)
    fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [backend])
    providers = build_oauth_providers(settings)

    router = APIRouter()
    auth_routers = [
        fastapi_users.get_auth_router(backend),
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
        router.include_router(
            fastapi_users.get_oauth_router(
                provider.client,
                backend,
                settings.secret_key.get_secret_value(),
                redirect_url=provider.redirect_url(settings),
                # The e-mail address is the account identity: a provider login with the
                # address of an existing account signs in to that account.
                associate_by_email=True,
                is_verified_by_default=True,
                csrf_token_cookie_secure=settings.secure_cookies,
            ),
            prefix=f"/auth/{provider.name}",
            tags=["auth"],
        )

    provider_list = [
        OAuthProviderOut(name=provider.name, display_name=provider.display_name)
        for provider in providers
    ]

    @router.get("/auth/providers", response_model=list[OAuthProviderOut], tags=["auth"])
    async def list_oauth_providers() -> list[OAuthProviderOut]:
        """OAuth providers enabled on this server, for rendering sign-in buttons."""
        return provider_list

    return router
