"""Аварийный вход для hr_admin — независим от auth_provider (работает даже
если Kerberos/SPNEGO сломан или ещё не настроен). Проверяется первым в
get_current_user, до какой-либо логики dev/kerberos: если оба заголовка
присутствуют, они полностью определяют identity, штатный провайдер не
вызывается вовсе.

Пароль — общий секрет из .env (ADMIN_FALLBACK_PASSWORD), не привязан к
конкретному пользователю сам по себе; кто именно войдёт — определяется
email в заголовке, но только если у этого пользователя ПРЯМО СЕЙЧАС есть
роль hr_admin (см. dependencies.py) — так что знание пароля само по себе
не даёт войти под кем угодно, только под уже существующим hr_admin."""

import hmac

from app.config import settings

FALLBACK_EMAIL_HEADER = "X-Admin-Fallback-Email"
FALLBACK_PASSWORD_HEADER = "X-Admin-Fallback-Password"


def check_password(password: str) -> bool:
    configured = settings.admin_fallback_password
    if not configured:
        return False
    return hmac.compare_digest(password, configured)
