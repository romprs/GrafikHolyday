import uuid
from datetime import date

from fastapi import APIRouter

from app.dependencies import CurrentUser, DbSession
from app.schemas.org_load import OrgLoadDetailOut, OrgLoadOut
from app.services import org_load_service, restriction_settings_service

router = APIRouter(prefix="/org-load", tags=["org-load"])


def _resolve_range(
    db: DbSession, date_from: date | None, date_to: date | None
) -> tuple[date, date]:
    if date_from is not None and date_to is not None:
        return date_from, date_to
    year = restriction_settings_service.get_planning_year(db)
    return date_from or date(year, 1, 1), date_to or date(year, 12, 31)


@router.get("", response_model=OrgLoadOut)
def get_org_load(
    org_unit_id: uuid.UUID,
    db: DbSession,
    _: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
) -> OrgLoadOut:
    date_from, date_to = _resolve_range(db, date_from, date_to)
    return org_load_service.get_org_load(db, org_unit_id, date_from, date_to)


@router.get("/detail", response_model=OrgLoadDetailOut)
def get_org_load_detail(
    org_unit_id: uuid.UUID,
    db: DbSession,
    _: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
) -> OrgLoadDetailOut:
    date_from, date_to = _resolve_range(db, date_from, date_to)
    return org_load_service.get_org_leave_detail(db, org_unit_id, date_from, date_to)
