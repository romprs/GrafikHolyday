import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.leave_balance import LeaveBalance
from app.models.leave_request import APPROVED, DRAFT, PENDING_APPROVAL, LeaveRequest
from app.models.user import User


def _days_in_year(request: LeaveRequest, year: int) -> int:
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    overlap_start = max(request.date_from, year_start)
    overlap_end = min(request.date_to, year_end)
    if overlap_start > overlap_end:
        return 0
    return (overlap_end - overlap_start).days + 1


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
    used = sum(_days_in_year(r, year) for r in approved_requests)

    return {
        "year": year,
        "accrued_days": accrued,
        "carried_over_days": carried_over,
        "used_days": used,
        "remaining_days": accrued + carried_over - used,
    }


def get_remaining_for_new_request(
    db: Session, user: User, year: int, exclude_request_ids: set[uuid.UUID] | None = None
) -> float:
    """Остаток с учётом уже поданных (pending_approval) и ещё не отправленных
    черновиков (draft), а не только согласованных заявок — чтобы нельзя было
    "закредитовать" баланс несколькими ещё не рассмотренными или даже не
    отправленными периодами сверх доступного."""
    balance = db.scalar(
        select(LeaveBalance).where(LeaveBalance.user_id == user.id, LeaveBalance.year == year)
    )
    accrued = float(balance.accrued_days) if balance else 0.0
    carried_over = float(balance.carried_over_days) if balance else 0.0

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    reserved_requests = db.scalars(
        select(LeaveRequest).where(
            LeaveRequest.user_id == user.id,
            LeaveRequest.status.in_((APPROVED, PENDING_APPROVAL, DRAFT)),
            LeaveRequest.date_from <= year_end,
            LeaveRequest.date_to >= year_start,
        )
    ).all()
    exclude = exclude_request_ids or set()
    reserved = sum(_days_in_year(r, year) for r in reserved_requests if r.id not in exclude)

    return accrued + carried_over - reserved


def set_balance(
    db: Session, actor: User, user: User, year: int, accrued_days: float, carried_over_days: float
) -> LeaveBalance:
    """HR проставляет начисленные дни вручную — до готовности выгрузки из
    внешней системы (см. app/sync)."""
    balance = db.scalar(
        select(LeaveBalance).where(LeaveBalance.user_id == user.id, LeaveBalance.year == year)
    )
    if balance is None:
        balance = LeaveBalance(user_id=user.id, year=year, accrued_days=accrued_days)
        db.add(balance)
    balance.accrued_days = accrued_days
    balance.carried_over_days = carried_over_days
    balance.updated_by = actor.id
    db.commit()
    db.refresh(balance)
    return balance
