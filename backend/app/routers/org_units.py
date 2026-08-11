from fastapi import APIRouter
from sqlalchemy import select

from app.dependencies import CurrentUser, DbSession
from app.models.org_unit import OrgUnit
from app.schemas.org_unit import OrgUnitEmployeeOut, OrgUnitOut
from app.services import user_admin_service

router = APIRouter(prefix="/org-units", tags=["org-units"])


@router.get("", response_model=list[OrgUnitOut])
def list_org_units(db: DbSession, _: CurrentUser) -> list[OrgUnitOut]:
    units = db.scalars(select(OrgUnit).where(OrgUnit.is_active).order_by(OrgUnit.name)).all()
    return list(units)


@router.get("/employees", response_model=list[OrgUnitEmployeeOut])
def list_org_unit_employees(db: DbSession, _: CurrentUser) -> list[OrgUnitEmployeeOut]:
    """Привязка сотрудник → подразделение, для отображения оргструктуры
    целиком (не только список юнитов)."""
    return [
        OrgUnitEmployeeOut(
            id=u.id, full_name=u.full_name, email=u.email, org_unit_id=u.org_unit_id, role=role
        )
        for u, role in user_admin_service.list_users_with_roles(db)
        if u.is_active
    ]
