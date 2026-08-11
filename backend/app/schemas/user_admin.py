import uuid

from pydantic import BaseModel


class UserWithRoleOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    org_unit_id: uuid.UUID | None
    has_benefits: bool
    is_active: bool
    role: str
    employee_code: str | None = None


class EmployeeCodeIn(BaseModel):
    employee_code: str | None = None
