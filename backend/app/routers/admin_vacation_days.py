from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.exceptions import ValidationFailedError
from app.dependencies import DbSession, require_role
from app.models.sync import KIND_VACATION_DAYS, SyncRun
from app.models.user import User
from app.schemas.sync import SyncRunOut
from app.services import (
    permissions,
    restriction_settings_service,
    sync_service,
    vacation_days_sync_service,
)

router = APIRouter(prefix="/admin/vacation-days", tags=["admin-vacation-days"])

HrAdmin = Annotated[User, Depends(require_role(permissions.HR_ADMIN))]


@router.post("/run", response_model=SyncRunOut)
def trigger_vacation_days_sync(db: DbSession, user: HrAdmin) -> SyncRunOut:
    client = vacation_days_sync_service.build_client(db)
    if client is None:
        raise ValidationFailedError("Источник дней отпуска не настроен, выключен или не задан URL")
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


@router.delete("/runs", status_code=204)
def clear_vacation_days_runs(db: DbSession, _: HrAdmin) -> None:
    sync_service.clear_history(db, KIND_VACATION_DAYS)
