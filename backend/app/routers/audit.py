from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.dependencies import DbSession, require_role
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogOut
from app.services import permissions

router = APIRouter(prefix="/admin/audit-log", tags=["admin-audit"])

HrAdmin = Annotated[User, Depends(require_role(permissions.HR_ADMIN))]


@router.get("", response_model=list[AuditLogOut])
def list_audit_log(db: DbSession, _: HrAdmin) -> list[AuditLogOut]:
    return list(db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc())).all())
