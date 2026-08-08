import uuid

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    org_unit_id: uuid.UUID | None
    has_benefits: bool
    is_active: bool


class CurrentUserOut(UserOut):
    role: str  # "employee" | "manager" | "hr_admin"
