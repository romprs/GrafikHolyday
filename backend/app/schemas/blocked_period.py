import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class BlockedPeriodCreate(BaseModel):
    date_from: date
    date_to: date
    reason: str
    scope: str
    org_unit_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None


class BlockedPeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date_from: date
    date_to: date
    reason: str
    scope: str
    org_unit_id: uuid.UUID | None
    user_id: uuid.UUID | None
    is_active: bool
    created_by: uuid.UUID
