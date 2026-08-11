import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.dependencies import CurrentUser, DbSession, require_role
from app.models.user import User
from app.schemas.delegation import DelegationTargetOut, LeaveDelegationCreate, LeaveDelegationOut
from app.services import delegation_service, permissions

router = APIRouter(prefix="/delegations", tags=["delegations"])

ManagerOrHrAdmin = Annotated[
    User, Depends(require_role(permissions.MANAGER, permissions.HR_ADMIN))
]


@router.get("", response_model=list[LeaveDelegationOut])
def list_delegations(db: DbSession, user: ManagerOrHrAdmin) -> list[LeaveDelegationOut]:
    return delegation_service.list_visible(db, user)


@router.get("/directory", response_model=list[DelegationTargetOut])
def list_directory(db: DbSession, _: ManagerOrHrAdmin) -> list[DelegationTargetOut]:
    """Полный список активных сотрудников — для выбора делегата, который
    может быть из любого подразделения (в отличие от цели делегирования,
    ограниченной зоной ответственности — см. list_org_unit_employees)."""
    return [
        DelegationTargetOut(id=u.id, full_name=u.full_name, email=u.email)
        for u in db.scalars(select(User).where(User.is_active).order_by(User.full_name)).all()
    ]


@router.post("", response_model=LeaveDelegationOut)
def create_delegation(
    body: LeaveDelegationCreate, db: DbSession, user: ManagerOrHrAdmin
) -> LeaveDelegationOut:
    return delegation_service.grant(db, user, body.delegate_user_id, body.target_user_id)


@router.delete("/{delegation_id}", status_code=204)
def revoke_delegation(delegation_id: uuid.UUID, db: DbSession, user: ManagerOrHrAdmin) -> None:
    delegation_service.revoke(db, user, delegation_id)


@router.get("/my-targets", response_model=list[DelegationTargetOut])
def list_my_targets(db: DbSession, user: CurrentUser) -> list[DelegationTargetOut]:
    """Сотрудники, за которых текущий пользователь может подавать/вести
    заявки — для переключателя "от чьего имени" на форме заявки."""
    return [
        DelegationTargetOut(id=u.id, full_name=u.full_name, email=u.email)
        for u in delegation_service.list_targets_for_delegate(db, user)
    ]
