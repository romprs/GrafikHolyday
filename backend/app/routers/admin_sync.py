from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.dependencies import DbSession, require_role
from app.models.sync import SyncRun
from app.models.user import User
from app.schemas.sync import SyncRunOut
from app.services import permissions, sync_service
from app.sync.fake_client import FakeDirectoryClient

router = APIRouter(prefix="/admin/sync", tags=["admin-sync"])

HrAdmin = Annotated[User, Depends(require_role(permissions.HR_ADMIN))]


@router.post("/run", response_model=SyncRunOut)
def trigger_sync(db: DbSession, user: HrAdmin) -> SyncRunOut:
    # FakeDirectoryClient — заглушка до готовности контракта реального API
    # (app/sync/rest_client.py); подмена клиента не требует изменений здесь.
    client = FakeDirectoryClient()
    return sync_service.run_sync(db, client, trigger_type="manual", triggered_by=user.id)


@router.get("/runs", response_model=list[SyncRunOut])
def list_sync_runs(db: DbSession, _: HrAdmin) -> list[SyncRunOut]:
    return list(db.scalars(select(SyncRun).order_by(SyncRun.started_at.desc())).all())
