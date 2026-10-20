import uuid

from fastapi_users import schemas
from pydantic import BaseModel, EmailStr


class UserRead(schemas.BaseUser[uuid.UUID]):
    pass


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass


class OAuthProviderOut(BaseModel):
    name: str
    display_name: str


class OAuthEmailConfirmationSent(BaseModel):
    """The provider sign-in is paused until the link e-mailed to `email` is opened."""

    email: EmailStr


class OAuthLinkConfirm(BaseModel):
    token: str
