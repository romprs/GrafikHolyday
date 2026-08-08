import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import CurrentUser, DbSession, require_role
from app.models.user import User
from app.schemas.blocked_period import BlockedPeriodCreate, BlockedPeriodOut
from app.services import blocked_period_service, permissions

router = APIRouter(prefix="/blocked-periods", tags=["blocked-periods"])

ManagerOrHrAdmin = Annotated[
    User, Depends(require_role(permissions.MANAGER, permissions.HR_ADMIN))
]


@router.get("", response_model=list[BlockedPeriodOut])
def list_blocked_periods(db: DbSession, _: CurrentUser) -> list[BlockedPeriodOut]:
    return blocked_period_service.list_all(db)


@router.post("", response_model=BlockedPeriodOut)
def create_blocked_period(
    body: BlockedPeriodCreate, db: DbSession, user: ManagerOrHrAdmin
) -> BlockedPeriodOut:
    return blocked_period_service.create(
        db,
        user,
        body.date_from,
        body.date_to,
        body.reason,
        body.scope,
        body.org_unit_id,
        body.user_id,
    )


@router.delete("/{blocked_period_id}", status_code=204)
def delete_blocked_period(
    blocked_period_id: uuid.UUID, db: DbSession, user: ManagerOrHrAdmin
) -> None:
    blocked_period_service.deactivate(db, user, blocked_period_id)
