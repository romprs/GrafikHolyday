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
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[BlockedRangeOut]:
    # date.today() как значение по умолчанию в сигнатуре вычислился бы один раз
    # при старте процесса (классическая ловушка Python), а не на каждый запрос —
    # поэтому резолвим "сегодня" внутри тела функции.
    resolved_from = date_from or date.today()
    resolved_to = date_to or (resolved_from + timedelta(days=365))
    blocks = blocked_period_service.get_effective_blocks(db, user, resolved_from, resolved_to)
    return [
        BlockedRangeOut(date_from=b.date_from, date_to=b.date_to, reason=b.reason) for b in blocks
    ]


@router.get("/team", response_model=list[TeamLeaveOut])
def get_team_calendar(
    db: DbSession,
    user: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[TeamLeaveOut]:
    resolved_from = date_from or date.today()
    resolved_to = date_to or (resolved_from + timedelta(days=90))
    requests = leave_request_service.list_team_leave(db, user, resolved_from, resolved_to)
    return [
        TeamLeaveOut(user_id=r.user_id, date_from=r.date_from, date_to=r.date_to, status=r.status)
        for r in requests
    ]
