from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import kerberos_provider
from app.auth.admin_fallback import check_password
from app.auth.dev_provider import resolve_dev_identity
from app.config import settings
from app.core.exceptions import ForbiddenError
from app.database import get_db
from app.models.user import User
from app.services import permissions

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    request: Request,
    db: DbSession,
    x_dev_user_id: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
    x_admin_fallback_email: Annotated[str | None, Header()] = None,
    x_admin_fallback_password: Annotated[str | None, Header()] = None,
) -> User:
    # Аварийный вход — проверяется раньше и независимо от auth_provider,
    # см. app/auth/admin_fallback.py. Присутствие обоих заголовков полностью
    # определяет исход запроса (не откатываемся на dev/kerberos при неудаче
    # — иначе неверный пароль выглядел бы как "пользователь не найден").
    if x_admin_fallback_email and x_admin_fallback_password:
        if not check_password(x_admin_fallback_password):
            raise ForbiddenError("Неверный пароль аварийного входа")
        user = db.scalar(
            select(User).where(User.email.ilike(x_admin_fallback_email), User.is_active)
        )
        if user is None:
            raise ForbiddenError("Пользователь для аварийного входа не найден или деактивирован")
        if permissions.resolve_role(db, user) != permissions.HR_ADMIN:
            raise ForbiddenError(
                "Аварийный вход доступен только для учётной записи с ролью HR-admin"
            )
        return user

    if settings.auth_provider == "dev":
        identity = resolve_dev_identity(x_dev_user_id)
        user = db.scalar(select(User).where(User.id == identity.user_id, User.is_active))
    elif settings.auth_provider == "kerberos":
        if settings.kerberos_mode == "nginx":
            raw = request.headers.get(settings.kerberos_trusted_header)
            if not raw:
                raise ForbiddenError(
                    f"Отсутствует заголовок {settings.kerberos_trusted_header} — запрос должен "
                    "идти через nginx с настроенным mod_auth_gssapi"
                )
            login = kerberos_provider.login_from_trusted_header(raw)
        elif settings.kerberos_mode == "python":
            login = kerberos_provider.get_gssapi_provider().authenticate(authorization)
        else:
            raise ForbiddenError(f"Неизвестный режим KERBEROS_MODE: {settings.kerberos_mode!r}")
        user = kerberos_provider.resolve_login(db, login)
    else:
        raise ForbiddenError("Провайдер аутентификации не поддерживается")

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
