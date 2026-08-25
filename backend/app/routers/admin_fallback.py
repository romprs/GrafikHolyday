"""Не часть публичного API — эндпоинт существует только для nginx
auth_request при KERBEROS_MODE=nginx (см. nginx-gssapi.conf.example,
satisfy any + auth_request). Сама аутентификация запроса всё равно
происходит штатно в get_current_user на основном проксируемом запросе —
этот эндпоинт лишь решает для nginx, пропускать запрос дальше или нет,
когда валидного SPNEGO-тикета нет."""

from typing import Annotated

from fastapi import APIRouter, Header

from app.auth.admin_fallback import resolve_admin_fallback
from app.dependencies import DbSession

router = APIRouter(prefix="/auth/admin-fallback", tags=["auth-admin-fallback"])


@router.get("/check")
def check_admin_fallback(
    db: DbSession,
    x_admin_fallback_email: Annotated[str | None, Header()] = None,
    x_admin_fallback_password: Annotated[str | None, Header()] = None,
) -> dict:
    resolve_admin_fallback(db, x_admin_fallback_email, x_admin_fallback_password)
    return {"ok": True}
