"""Аварийный вход для hr_admin — независим от auth_provider (работает даже
если Kerberos/SPNEGO сломан или ещё не настроен). Проверяется первым в
get_current_user, до какой-либо логики dev/kerberos: если оба заголовка
присутствуют, они полностью определяют identity, штатный провайдер не
вызывается вовсе.

Пароль — общий секрет из .env (ADMIN_FALLBACK_PASSWORD), не привязан к
конкретному пользователю сам по себе; кто именно войдёт — определяется
email в заголовке, но только если у этого пользователя ПРЯМО СЕЙЧАС есть
роль hr_admin (см. resolve_admin_fallback) — так что знание пароля само по
себе не даёт войти под кем угодно, только под уже существующим hr_admin.

При KERBEROS_MODE=nginx этих заголовков бэкенд никогда не увидит для
запросов, отклонённых auth_gssapi раньше — см. app/routers/admin_fallback.py
и nginx-gssapi.conf.example (satisfy any + auth_request), где та же
проверка используется как "пропускной" эндпоинт для nginx."""

import hmac

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import ForbiddenError
from app.models.user import User
from app.services import permissions

FALLBACK_EMAIL_HEADER = "X-Admin-Fallback-Email"
FALLBACK_PASSWORD_HEADER = "X-Admin-Fallback-Password"


def check_password(password: str) -> bool:
    configured = settings.admin_fallback_password
    if not configured:
        return False
    return hmac.compare_digest(password, configured)


def resolve_admin_fallback(db: Session, email: str | None, password: str | None) -> User:
    """Общая проверка для обоих потребителей (get_current_user и
    routers/admin_fallback.check — см. модуль docstring). Бросает
    ForbiddenError при любой неудаче, иначе возвращает пользователя."""
    if not email or not password:
        raise ForbiddenError("Не указаны email или пароль аварийного входа")
    if not check_password(password):
        raise ForbiddenError("Неверный пароль аварийного входа")
    user = db.scalar(select(User).where(User.email.ilike(email), User.is_active))
    if user is None:
        raise ForbiddenError("Пользователь для аварийного входа не найден или деактивирован")
    if permissions.resolve_role(db, user) != permissions.HR_ADMIN:
        raise ForbiddenError("Аварийный вход доступен только для учётной записи с ролью HR-admin")
    return user
