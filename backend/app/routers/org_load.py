import uuid
from datetime import date

from fastapi import APIRouter

from app.core.exceptions import ForbiddenError
from app.dependencies import CurrentUser, DbSession
from app.schemas.org_load import OrgLoadDetailOut, OrgLoadOut
from app.services import org_load_service, org_unit_service, restriction_settings_service

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
    user: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
) -> OrgLoadOut:
    """Агрегат без имён — поэтому доступен и рядовому сотруднику, но только
    для его собственного подразделения (для просмотра загруженности отдела
    в своей вкладке). Детализация с именами — только руководителю/HR, см.
    get_org_load_detail."""
    date_from, date_to = _resolve_range(db, date_from, date_to)
    visible = org_unit_service.visible_unit_ids(db, user)
    allowed = visible is None or org_unit_id in visible or org_unit_id == user.org_unit_id
    if not allowed:
        raise ForbiddenError("Нет доступа к загруженности этого подразделения")
    return org_load_service.get_org_load(db, org_unit_id, date_from, date_to)


@router.get("/detail", response_model=OrgLoadDetailOut)
def get_org_load_detail(
    org_unit_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
) -> OrgLoadDetailOut:
    date_from, date_to = _resolve_range(db, date_from, date_to)
    visible = org_unit_service.visible_unit_ids(db, user)
    if not (visible is None or org_unit_id in visible):
        raise ForbiddenError("Нет доступа к детализации загруженности этого подразделения")
    return org_load_service.get_org_leave_detail(db, org_unit_id, date_from, date_to)
