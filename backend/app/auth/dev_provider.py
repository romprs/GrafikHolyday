import uuid

from app.auth.interface import AuthenticatedIdentity, AuthProvider
from app.core.exceptions import ForbiddenError

DEV_HEADER = "X-Dev-User-Id"


class DevAuthProvider(AuthProvider):
    """Только для локальной разработки: identity берётся из заголовка X-Dev-User-Id,
    который фронтенд проставляет после выбора тестового пользователя в дев-логине.
    """

    def resolve_identity(self, authorization_header: str | None) -> AuthenticatedIdentity:
        raise NotImplementedError("dev provider reads a custom header, see dependencies.py")


def resolve_dev_identity(dev_user_id: str | None) -> AuthenticatedIdentity:
    if not dev_user_id:
        raise ForbiddenError(
            "Не выбран пользователь для входа (dev-режим)", {"header": DEV_HEADER}
        )
    try:
        return AuthenticatedIdentity(user_id=uuid.UUID(dev_user_id))
    except ValueError as exc:
        raise ForbiddenError("Некорректный идентификатор пользователя (dev-режим)") from exc
