from fastapi import APIRouter
from sqlalchemy import select

from app.dependencies import CurrentUser, DbSession
from app.models.org_unit import OrgUnit
from app.schemas.org_unit import OrgUnitEmployeeOut, OrgUnitOut
from app.services import org_unit_service, user_admin_service

router = APIRouter(prefix="/org-units", tags=["org-units"])


@router.get("", response_model=list[OrgUnitOut])
def list_org_units(db: DbSession, user: CurrentUser) -> list[OrgUnitOut]:
    """Рядовой сотрудник оргструктуру не видит вовсе; руководитель видит
    только свою ветку (свой юнит и всё, что ниже — см.
    org_unit_service.visible_unit_ids); HR/админ — всё."""
    visible = org_unit_service.visible_unit_ids(db, user)
    query = select(OrgUnit).where(OrgUnit.is_active).order_by(OrgUnit.name)
    if visible is not None:
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
