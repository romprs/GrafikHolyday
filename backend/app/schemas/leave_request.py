import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class LeaveRequestCreate(BaseModel):
    date_from: date
    date_to: date
    comment: str | None = None


class LeaveRequestReview(BaseModel):
    comment: str | None = None


class LeaveRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    date_from: date
    date_to: date
    comment: str | None
    status: str
    reviewer_id: uuid.UUID | None
    review_comment: str | None
    submitted_at: datetime | None
    reviewed_at: datetime | None
    cancelled_at: datetime | None
    days: int


class LeaveBalanceOut(BaseModel):
    year: int
    accrued_days: float
    carried_over_days: float
    used_days: int
    remaining_days: float
