import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.dependencies import CurrentUser, DbSession, require_role
from app.models.org_unit import OrgUnit
from app.models.user import User
from app.schemas.org_unit import OrgUnitCreate, OrgUnitEmployeeOut, OrgUnitOut, OrgUnitUpdate
from app.services import org_unit_service, permissions, user_admin_service

router = APIRouter(prefix="/org-units", tags=["org-units"])

HrAdmin = Annotated[User, Depends(require_role(permissions.HR_ADMIN))]


@router.get("", response_model=list[OrgUnitOut])
def list_org_units(db: DbSession, user: CurrentUser) -> list[OrgUnitOut]:
    """Рядовой сотрудник оргструктуру не видит вовсе; руководитель видит
    только свою активную ветку (свой юнит и всё, что ниже — см.
    org_unit_service.visible_unit_ids); HR/админ — всё, включая
    деактивированные подразделения — иначе их нельзя ни найти, ни
    реактивировать (кнопка «деактивировать» на странице становится
    билетом в один конец)."""
    visible = org_unit_service.visible_unit_ids(db, user)
    query = select(OrgUnit).order_by(OrgUnit.name)
    if visible is not None:
        query = query.where(OrgUnit.is_active)
        if not visible:
            return []
        query = query.where(OrgUnit.id.in_(visible))
    return list(db.scalars(query).all())


@router.get("/employees", response_model=list[OrgUnitEmployeeOut])
def list_org_unit_employees(db: DbSession, user: CurrentUser) -> list[OrgUnitEmployeeOut]:
    """Привязка сотрудник → подразделение — тем же правилом видимости, что
    и list_org_units (см. там)."""
    visible = org_unit_service.visible_unit_ids(db, user)
    if visible is not None and not visible:
        return []
    return [
        OrgUnitEmployeeOut(
            id=u.id, full_name=u.full_name, email=u.email, org_unit_id=u.org_unit_id, role=role
        )
        for u, role in user_admin_service.list_users_with_roles(db)
        if u.is_active and (visible is None or u.org_unit_id in visible)
    ]


@router.post("", response_model=OrgUnitOut)
def create_org_unit(body: OrgUnitCreate, db: DbSession, _: HrAdmin) -> OrgUnitOut:
    return org_unit_service.create(db, body.name, body.unit_kind, body.parent_id, body.head_user_id)


@router.patch("/{unit_id}", response_model=OrgUnitOut)
def update_org_unit(
    unit_id: uuid.UUID, body: OrgUnitUpdate, db: DbSession, _: HrAdmin
) -> OrgUnitOut:
    return org_unit_service.update(
        db, unit_id, body.name, body.unit_kind, body.parent_id, body.head_user_id, body.is_active
    )


@router.delete("/{unit_id}", response_model=OrgUnitOut)
def delete_org_unit(unit_id: uuid.UUID, db: DbSession, _: HrAdmin) -> OrgUnitOut:
    return org_unit_service.deactivate(db, unit_id)
