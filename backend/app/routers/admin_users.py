import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import DbSession, require_role
from app.models.user import User
from app.schemas.user_admin import UserWithRoleOut
from app.services import permissions, user_admin_service

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

HrAdmin = Annotated[User, Depends(require_role(permissions.HR_ADMIN))]


@router.get("", response_model=list[UserWithRoleOut])
def list_users(db: DbSession, _: HrAdmin) -> list[UserWithRoleOut]:
    return [
        UserWithRoleOut(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            org_unit_id=u.org_unit_id,
            has_benefits=u.has_benefits,
            is_active=u.is_active,
            role=role,
        )
        for u, role in user_admin_service.list_users_with_roles(db)
    ]


@router.post("/{user_id}/roles/{role}", status_code=204)
def grant_role(user_id: uuid.UUID, role: str, db: DbSession, actor: HrAdmin) -> None:
    user_admin_service.grant_role(db, actor, user_id, role)


@router.delete("/{user_id}/roles/{role}", status_code=204)
def revoke_role(user_id: uuid.UUID, role: str, db: DbSession, actor: HrAdmin) -> None:
    user_admin_service.revoke_role(db, actor, user_id, role)
