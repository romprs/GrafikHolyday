from datetime import date, timedelta

from fastapi import APIRouter

from app.dependencies import CurrentUser, DbSession
from app.schemas.calendar import BlockedRangeOut, TeamLeaveOut
from app.services import blocked_period_service, leave_request_service

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/blocked", response_model=list[BlockedRangeOut])
def get_blocked_ranges(
    db: DbSession,
    user: CurrentUser,
    date_from: date = date.today(),
    date_to: date = date.today() + timedelta(days=365),
) -> list[BlockedRangeOut]:
    blocks = blocked_period_service.get_effective_blocks(db, user, date_from, date_to)
    return [
        BlockedRangeOut(date_from=b.date_from, date_to=b.date_to, reason=b.reason) for b in blocks
    ]


@router.get("/team", response_model=list[TeamLeaveOut])
def get_team_calendar(
    db: DbSession,
    user: CurrentUser,
    date_from: date = date.today(),
    date_to: date = date.today() + timedelta(days=90),
) -> list[TeamLeaveOut]:
    requests = leave_request_service.list_team_leave(db, user, date_from, date_to)
    return [
        TeamLeaveOut(user_id=r.user_id, date_from=r.date_from, date_to=r.date_to, status=r.status)
        for r in requests
    ]
