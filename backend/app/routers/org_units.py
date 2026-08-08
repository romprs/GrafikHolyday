from fastapi import APIRouter
from sqlalchemy import select

from app.dependencies import CurrentUser, DbSession
from app.models.org_unit import OrgUnit
from app.schemas.org_unit import OrgUnitOut

router = APIRouter(prefix="/org-units", tags=["org-units"])


@router.get("", response_model=list[OrgUnitOut])
def list_org_units(db: DbSession, _: CurrentUser) -> list[OrgUnitOut]:
    units = db.scalars(select(OrgUnit).where(OrgUnit.is_active).order_by(OrgUnit.name)).all()
    return list(units)
