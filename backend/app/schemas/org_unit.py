import uuid

from pydantic import BaseModel, ConfigDict


class OrgUnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    unit_kind: str | None
    head_user_id: uuid.UUID | None
    is_active: bool


class OrgUnitEmployeeOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    org_unit_id: uuid.UUID | None
    role: str


class OrgUnitCreate(BaseModel):
    name: str
    unit_kind: str | None = None
    parent_id: uuid.UUID | None = None
    head_user_id: uuid.UUID | None = None


class OrgUnitUpdate(BaseModel):
    name: str
    unit_kind: str | None = None
    parent_id: uuid.UUID | None = None
    head_user_id: uuid.UUID | None = None
    is_active: bool = True
