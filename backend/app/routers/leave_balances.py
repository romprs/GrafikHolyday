import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.exceptions import NotFoundError
from app.dependencies import CurrentUser, DbSession, require_role
from app.models.user import User
from app.schemas.leave_request import LeaveBalanceOut, LeaveBalanceSet
from app.services import leave_balance_service, permissions, restriction_settings_service

router = APIRouter(prefix="/leave-balances", tags=["leave-balances"])

HrAdmin = Annotated[User, Depends(require_role(permissions.HR_ADMIN))]


@router.get("/me", response_model=LeaveBalanceOut)
def get_my_balance(db: DbSession, user: CurrentUser, year: int | None = None) -> LeaveBalanceOut:
    resolved_year = year if year is not None else restriction_settings_service.get_planning_year(db)
    return leave_balance_service.get_summary(db, user, resolved_year)


@router.get("/{user_id}", response_model=LeaveBalanceOut)
def get_user_balance(
    user_id: uuid.UUID, db: DbSession, _: HrAdmin, year: int | None = None
) -> LeaveBalanceOut:
    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("Сотрудник не найден")
    resolved_year = year if year is not None else restriction_settings_service.get_planning_year(db)
    return leave_balance_service.get_summary(db, target, resolved_year)


@router.put("/{user_id}", response_model=LeaveBalanceOut)
def set_user_balance(
    user_id: uuid.UUID, body: LeaveBalanceSet, db: DbSession, actor: HrAdmin
) -> LeaveBalanceOut:
    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("Сотрудник не найден")
    balance = leave_balance_service.set_balance(
        db, actor, target, body.year, body.accrued_days, body.carried_over_days
    )
    return leave_balance_service.get_summary(db, target, balance.year)
