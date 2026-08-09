import uuid
from datetime import date

from fastapi import APIRouter

from app.dependencies import CurrentUser, DbSession
from app.schemas.org_load import OrgLoadOut
from app.services import org_load_service, restriction_settings_service

router = APIRouter(prefix="/org-load", tags=["org-load"])


@router.get("", response_model=OrgLoadOut)
def get_org_load(
    org_unit_id: uuid.UUID,
    db: DbSession,
    _: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
) -> OrgLoadOut:
    if date_from is None or date_to is None:
        year = restriction_settings_service.get_planning_year(db)
        date_from = date_from or date(year, 1, 1)
        date_to = date_to or date(year, 12, 31)
    return org_load_service.get_org_load(db, org_unit_id, date_from, date_to)
