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
