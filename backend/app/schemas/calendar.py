import uuid
from datetime import date

from pydantic import BaseModel


class BlockedRangeOut(BaseModel):
    date_from: date
    date_to: date
    reason: str


class TeamLeaveOut(BaseModel):
    user_id: uuid.UUID
    date_from: date
    date_to: date
    status: str
