import uuid
from datetime import date, timedelta

from fastapi import APIRouter

from app.dependencies import CurrentUser, DbSession
from app.schemas.org_load import OrgLoadOut
from app.services import org_load_service

router = APIRouter(prefix="/org-load", tags=["org-load"])


@router.get("", response_model=OrgLoadOut)
def get_org_load(
    org_unit_id: uuid.UUID,
    db: DbSession,
    _: CurrentUser,
    date_from: date = date.today(),
    date_to: date = date.today() + timedelta(days=60),
) -> OrgLoadOut:
    return org_load_service.get_org_load(db, org_unit_id, date_from, date_to)
