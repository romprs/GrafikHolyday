from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.leave_balance import LeaveBalance
from app.models.leave_request import APPROVED, LeaveRequest
from app.models.user import User


def get_summary(db: Session, user: User, year: int) -> dict:
    balance = db.scalar(
        select(LeaveBalance).where(LeaveBalance.user_id == user.id, LeaveBalance.year == year)
    )
    accrued = float(balance.accrued_days) if balance else 0.0
    carried_over = float(balance.carried_over_days) if balance else 0.0

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    approved_requests = db.scalars(
        select(LeaveRequest).where(
            LeaveRequest.user_id == user.id,
            LeaveRequest.status == APPROVED,
            LeaveRequest.date_from <= year_end,
            LeaveRequest.date_to >= year_start,
        )
    ).all()

    used = 0
    for request in approved_requests:
        overlap_start = max(request.date_from, year_start)
        overlap_end = min(request.date_to, year_end)
        used += (overlap_end - overlap_start).days + 1

    return {
        "year": year,
        "accrued_days": accrued,
        "carried_over_days": carried_over,
        "used_days": used,
        "remaining_days": accrued + carried_over - used,
    }
