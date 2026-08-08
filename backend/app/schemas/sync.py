import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SyncRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    trigger_type: str
    triggered_by: uuid.UUID | None
    status: str
    summary: dict
    error_message: str | None
