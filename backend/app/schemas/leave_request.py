import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class LeaveRequestCreate(BaseModel):
    date_from: date
    date_to: date
    comment: str | None = None
    bonus_requested: bool = False
    on_behalf_of: uuid.UUID | None = None


class LeaveRequestBonusUpdate(BaseModel):
    bonus_requested: bool


class LeaveRequestReview(BaseModel):
    comment: str | None = None


class LeaveRequestAdminOverride(BaseModel):
    reason: str
    date_from: date | None = None
    date_to: date | None = None
    status: str | None = None


class LeaveRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    date_from: date
    date_to: date
    comment: str | None
    status: str
    bonus_requested: bool
    submission_id: uuid.UUID | None
    acted_by: uuid.UUID | None
    reviewer_id: uuid.UUID | None
    review_comment: str | None
    submitted_at: datetime | None
    reviewed_at: datetime | None
    cancelled_at: datetime | None
    days: int


class LeaveRequestWithEmployeeOut(LeaveRequestOut):
    """LeaveRequestOut + ФИО сотрудника — для очереди согласования и списка
    согласованных заявок, где руководителю нужно видеть, чья это заявка."""

    user_full_name: str


class LeaveBalanceOut(BaseModel):
    year: int
    accrued_days: float
    carried_over_days: float
    used_days: int
    remaining_days: float


class LeaveBalanceSet(BaseModel):
    year: int
    accrued_days: float
    carried_over_days: float = 0
