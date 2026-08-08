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
