import uuid
from datetime import date

from pydantic import BaseModel


class OrgLoadDayOut(BaseModel):
    date: date
    on_leave: int
    headcount: int
    fraction: float
    band: str


class OrgLoadOut(BaseModel):
    org_unit_id: uuid.UUID
    headcount: int
    days: list[OrgLoadDayOut]


class OrgLoadEmployeeOut(BaseModel):
    id: uuid.UUID
    full_name: str
    role: str


class OrgLoadLeaveEntryOut(BaseModel):
    user_id: uuid.UUID
    date_from: date
    date_to: date
    status: str


class OrgLoadDetailOut(BaseModel):
    org_unit_id: uuid.UUID
    employees: list[OrgLoadEmployeeOut]
    leaves: list[OrgLoadLeaveEntryOut]
