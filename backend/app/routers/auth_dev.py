"""Только для dev-режима: список пользователей для выбора при "входе" без реального SSO."""

from fastapi import APIRouter
from sqlalchemy import select

from app.config import settings
from app.core.exceptions import ForbiddenError
from app.dependencies import DbSession
from app.models.user import User
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth/dev", tags=["auth-dev"])


@router.get("/users", response_model=list[UserOut])
def list_dev_login_users(db: DbSession) -> list[UserOut]:
    if settings.auth_provider != "dev":
        raise ForbiddenError("Dev-логин недоступен вне dev-режима")
    users = db.scalars(select(User).where(User.is_active).order_by(User.full_name)).all()
    return list(users)
