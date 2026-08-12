import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrgDirectoryImportIn(BaseModel):
    # Сырое содержимое файлов — ответ источника как есть (JSON с полем
    # "value"), см. app/integrations/org_directory.extract_value. Хотя бы
    # одно поле обязательно.
    departments: str | None = None
    employees: str | None = None


class SyncRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    kind: str
    trigger_type: str
    triggered_by: uuid.UUID | None
    status: str
    summary: dict
    error_message: str | None
