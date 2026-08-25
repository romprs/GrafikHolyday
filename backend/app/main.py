import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import register_exception_handlers

# Без этого логи из logging.getLogger(__name__) в сервисах/интеграциях (в
# частности — синхронизации, см. app/services/sync_service.py и
# app/integrations/org_directory.py) никуда не выводятся: у Python-логгера
# по умолчанию нет обработчика. basicConfig пишет в stdout, что при
# systemd-запуске (см. deploy/redos8) уходит в journalctl -u vacation-backend.
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
from app.routers import (
    admin_fallback,
    admin_study_periods,
    admin_sync,
    admin_users,
    admin_vacation_days,
    audit,
    auth_dev,
    blocked_periods,
    calendar,
    delegations,
    leave_balances,
    leave_requests,
    org_load,
    org_units,
    restriction_settings,
    users,
)

app = FastAPI(title="Планирование отпусков", version="0.1.0")


@app.on_event("startup")
def _validate_kerberos_config() -> None:
    # KERBEROS_MODE=python грузит keytab и собирает GSS-credentials один раз
    # здесь — чтобы битая конфигурация (нет python-gssapi, не задан
    # KERBEROS_SERVER_HOSTNAME/KERBEROS_KEYTAB_PATH, keytab не читается)
    # роняла запуск сервиса сразу, а не первый же вход пользователя.
    if settings.auth_provider == "kerberos" and settings.kerberos_mode == "python":
        from app.auth.kerberos_provider import get_gssapi_provider

        get_gssapi_provider()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(admin_fallback.router)
app.include_router(users.router)
app.include_router(org_units.router)
app.include_router(auth_dev.router)
app.include_router(leave_requests.router)
app.include_router(leave_balances.router)
app.include_router(blocked_periods.router)
app.include_router(calendar.router)
app.include_router(restriction_settings.router)
app.include_router(admin_sync.router)
app.include_router(org_load.router)
app.include_router(audit.router)
app.include_router(admin_users.router)
app.include_router(admin_study_periods.router)
app.include_router(admin_vacation_days.router)
app.include_router(delegations.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
