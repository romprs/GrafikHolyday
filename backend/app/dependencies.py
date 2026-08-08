from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dev_provider import resolve_dev_identity
from app.config import settings
from app.core.exceptions import ForbiddenError
from app.database import get_db
from app.models.user import User
from app.services import permissions

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    x_dev_user_id: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if settings.auth_provider == "dev":
        identity = resolve_dev_identity(x_dev_user_id)
    else:
        # Phase 5: OIDCAuthProvider().resolve_identity(authorization)
        raise ForbiddenError("Провайдер аутентификации не поддерживается")

    user = db.scalar(select(User).where(User.id == identity.user_id, User.is_active))
    if user is None:
        raise ForbiddenError("Пользователь не найден или деактивирован")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed_roles: str):
    def _checker(db: DbSession, user: CurrentUser) -> User:
        role = permissions.resolve_role(db, user)
        if role not in allowed_roles:
            raise ForbiddenError(
                "Недостаточно прав для этого действия",
                {"required_roles": list(allowed_roles), "actual_role": role},
            )
        return user

    return _checker
