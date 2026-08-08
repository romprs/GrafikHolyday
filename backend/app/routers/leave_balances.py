from datetime import date

from fastapi import APIRouter

from app.dependencies import CurrentUser, DbSession
from app.schemas.leave_request import LeaveBalanceOut
from app.services import leave_balance_service

router = APIRouter(prefix="/leave-balances", tags=["leave-balances"])


@router.get("/me", response_model=LeaveBalanceOut)
def get_my_balance(
    db: DbSession, user: CurrentUser, year: int = date.today().year
) -> LeaveBalanceOut:
    return leave_balance_service.get_summary(db, user, year)
