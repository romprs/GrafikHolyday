from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.exceptions import ValidationFailedError
from app.dependencies import DbSession, require_role
from app.integrations.org_directory import (
    FileDirectoryClient,
    OrgDirectoryClient,
    extract_value,
    parse_departments,
    parse_employees,
)
from app.models.restriction_settings import EXTERNAL_SOURCE_CONNECTION
from app.models.sync import KIND_ORG_DIRECTORY, SyncRun
from app.models.user import User
from app.schemas.sync import OrgDirectoryImportIn, SyncRunOut
from app.services import permissions, restriction_settings_service, sync_service
from app.sync.fake_client import FakeDirectoryClient
from app.sync.interface import ExternalDirectoryClient

router = APIRouter(prefix="/admin/sync", tags=["admin-sync"])

HrAdmin = Annotated[User, Depends(require_role(permissions.HR_ADMIN))]


def _build_client(db: DbSession) -> ExternalDirectoryClient:
    """Реальный клиент — как только источник включён и указан URL; иначе,
    как и раньше, тестовая фикстура (FakeDirectoryClient), чтобы синк
    оставался доступен для демо/локальной разработки без боевых реквизитов."""
    setting = restriction_settings_service.get(db, EXTERNAL_SOURCE_CONNECTION)
    if setting is None or not setting.enabled:
        return FakeDirectoryClient()
    departments_url = setting.params.get("departments_url") or ""
    if not departments_url:
        return FakeDirectoryClient()
    return OrgDirectoryClient(
        departments_url=departments_url,
        login=setting.params.get("auth_login") or "",
        password=setting.params.get("auth_password") or "",
        employees_url=setting.params.get("employees_url") or None,
        verify_tls=bool(setting.params.get("verify_tls", False)),
    )


@router.post("/import", response_model=SyncRunOut)
def import_org_directory_file(db: DbSession, user: HrAdmin, body: OrgDirectoryImportIn) -> SyncRunOut:
    if not body.departments and not body.employees:
        raise ValidationFailedError("Нужен хотя бы один файл — подразделения или сотрудники")
    try:
        org_units = parse_departments(extract_value(body.departments)) if body.departments else []
        users = parse_employees(extract_value(body.employees)) if body.employees else []
    except ValueError as exc:
        raise ValidationFailedError(str(exc)) from exc
    client = FileDirectoryClient(org_units=org_units, users=users)
    return sync_service.run_sync(db, client, trigger_type="manual", triggered_by=user.id)


@router.post("/run", response_model=SyncRunOut)
def trigger_sync(db: DbSession, user: HrAdmin) -> SyncRunOut:
    client = _build_client(db)
    return sync_service.run_sync(db, client, trigger_type="manual", triggered_by=user.id)


@router.get("/runs", response_model=list[SyncRunOut])
def list_sync_runs(db: DbSession, _: HrAdmin) -> list[SyncRunOut]:
    return list(
        db.scalars(
            select(SyncRun)
            .where(SyncRun.kind == KIND_ORG_DIRECTORY)
            .order_by(SyncRun.started_at.desc())
        ).all()
    )
