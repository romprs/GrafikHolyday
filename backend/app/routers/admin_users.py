import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import DbSession, require_role
from app.models.user import User
from app.schemas.user_admin import EmployeeCodeIn, UserCreate, UserUpdate, UserWithRoleOut
from app.services import permissions, user_admin_service

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

HrAdmin = Annotated[User, Depends(require_role(permissions.HR_ADMIN))]


def _with_role(u: User, role: str) -> UserWithRoleOut:
    return UserWithRoleOut(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        org_unit_id=u.org_unit_id,
        has_benefits=u.has_benefits,
        is_active=u.is_active,
        role=role,
        employee_code=u.employee_code,
    )


@router.get("", response_model=list[UserWithRoleOut])
def list_users(db: DbSession, _: HrAdmin) -> list[UserWithRoleOut]:
    return [_with_role(u, role) for u, role in user_admin_service.list_users_with_roles(db)]


@router.post("", response_model=UserWithRoleOut)
def create_user(body: UserCreate, db: DbSession, _: HrAdmin) -> UserWithRoleOut:
    user = user_admin_service.create_user(
        db, body.email, body.full_name, body.org_unit_id, body.has_benefits, body.employee_code
    )
    role = permissions.resolve_role(db, user)
    return _with_role(user, role)


@router.patch("/{user_id}", response_model=UserWithRoleOut)
def update_user(user_id: uuid.UUID, body: UserUpdate, db: DbSession, _: HrAdmin) -> UserWithRoleOut:
    user = user_admin_service.update_user(
        db, user_id, body.email, body.full_name, body.org_unit_id, body.has_benefits, body.is_active
    )
    role = permissions.resolve_role(db, user)
    return _with_role(user, role)


@router.delete("/{user_id}", response_model=UserWithRoleOut)
def delete_user(user_id: uuid.UUID, db: DbSession, _: HrAdmin) -> UserWithRoleOut:
    user = user_admin_service.deactivate_user(db, user_id)
    role = permissions.resolve_role(db, user)
    return _with_role(user, role)


@router.patch("/{user_id}/employee-code", response_model=UserWithRoleOut)
def set_employee_code(
    user_id: uuid.UUID, body: EmployeeCodeIn, db: DbSession, actor: HrAdmin
) -> UserWithRoleOut:
    user = user_admin_service.set_employee_code(db, user_id, body.employee_code)
    role = permissions.resolve_role(db, user)
    return _with_role(user, role)


@router.post("/{user_id}/roles/{role}", status_code=204)
def grant_role(user_id: uuid.UUID, role: str, db: DbSession, actor: HrAdmin) -> None:
    user_admin_service.grant_role(db, actor, user_id, role)


@router.delete("/{user_id}/roles/{role}", status_code=204)
def revoke_role(user_id: uuid.UUID, role: str, db: DbSession, actor: HrAdmin) -> None:
    user_admin_service.revoke_role(db, actor, user_id, role)
