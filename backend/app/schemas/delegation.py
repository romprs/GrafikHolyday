import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LeaveDelegationCreate(BaseModel):
    delegate_user_id: uuid.UUID
    target_user_id: uuid.UUID | None = None
    target_org_unit_id: uuid.UUID | None = None


class LeaveDelegationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scope: str
    delegate_user_id: uuid.UUID
    target_user_id: uuid.UUID | None
    target_org_unit_id: uuid.UUID | None
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    revoked_at: datetime | None


class DelegationTargetOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
