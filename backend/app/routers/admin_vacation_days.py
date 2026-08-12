from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.exceptions import ValidationFailedError
from app.dependencies import DbSession, require_role
from app.integrations.vacation_days import VacationDaysClient
from app.models.restriction_settings import VACATION_DAYS_SOURCE
from app.models.sync import KIND_VACATION_DAYS, SyncRun
from app.models.user import User
from app.schemas.sync import SyncRunOut
from app.services import permissions, restriction_settings_service, vacation_days_sync_service

router = APIRouter(prefix="/admin/vacation-days", tags=["admin-vacation-days"])

HrAdmin = Annotated[User, Depends(require_role(permissions.HR_ADMIN))]


@router.post("/run", response_model=SyncRunOut)
def trigger_vacation_days_sync(db: DbSession, user: HrAdmin) -> SyncRunOut:
    setting = restriction_settings_service.get(db, VACATION_DAYS_SOURCE)
    if setting is None or not setting.enabled:
        raise ValidationFailedError("Источник дней отпуска не настроен или выключен")
    base_url = setting.params.get("base_url") or ""
    if not base_url:
        raise ValidationFailedError("Не задан URL источника дней отпуска")

    client = VacationDaysClient(
        base_url=base_url,
        login=setting.params.get("auth_login") or "",
        password=setting.params.get("auth_password") or "",
        verify_tls=bool(setting.params.get("verify_tls", False)),
    )
    year = restriction_settings_service.get_planning_year(db)
    return vacation_days_sync_service.run_sync(db, client, year, "manual", user.id)


@router.get("/runs", response_model=list[SyncRunOut])
def list_vacation_days_runs(db: DbSession, _: HrAdmin) -> list[SyncRunOut]:
    return list(
        db.scalars(
            select(SyncRun)
            .where(SyncRun.kind == KIND_VACATION_DAYS)
            .order_by(SyncRun.started_at.desc())
        ).all()
    )
