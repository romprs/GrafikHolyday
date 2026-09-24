from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.dependencies import DbSession, require_role
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogOut
from app.services import audit_service, permissions

router = APIRouter(prefix="/admin/audit-log", tags=["admin-audit"])

HrAdmin = Annotated[User, Depends(require_role(permissions.HR_ADMIN))]


@router.get("", response_model=list[AuditLogOut])
def list_audit_log(db: DbSession, _: HrAdmin) -> list[AuditLogOut]:
    """Плюс имя исполнителя (performed_by_name) — иначе в журнале виден
    только сырой UUID, HR не может понять, кто на самом деле внёс правку."""
    entries = list(db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc())).all())
    performer_ids = {e.performed_by for e in entries}
    names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(performer_ids)))}
    return [
        AuditLogOut(
            id=e.id,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            action=e.action,
            performed_by=e.performed_by,
            performed_by_name=names.get(e.performed_by, "—"),
            reason=e.reason,
            before_state=e.before_state,
            after_state=e.after_state,
            created_at=e.created_at,
        )
        for e in entries
    ]


@router.delete("", status_code=204)
def clear_audit_log(
    db: DbSession,
    _: HrAdmin,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> None:
    audit_service.clear(db, date_from, date_to)
