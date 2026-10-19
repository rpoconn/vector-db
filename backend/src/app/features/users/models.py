from fastapi_users_db_sqlalchemy import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
)
from sqlalchemy.orm import Mapped, relationship

from app.shared.database import Base


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    """A Google/Microsoft identity linked to a user."""


class User(SQLAlchemyBaseUserTableUUID, Base):
    """An account, identified by its (case-insensitively unique) e-mail address.

    Password and OAuth sign-ins with the same address resolve to the same row.
    """

    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(lazy="joined")
