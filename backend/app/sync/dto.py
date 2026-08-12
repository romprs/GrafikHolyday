from pydantic import BaseModel


class ExternalOrgUnitDTO(BaseModel):
    external_id: str
    parent_external_id: str | None
    name: str
    unit_kind: str | None
    head_external_id: str | None  # external_id пользователя-руководителя


class ExternalUserDTO(BaseModel):
    external_id: str
    email: str
    full_name: str
    org_unit_external_id: str | None
    # None — источник не знает льготность (например, справочник сотрудников
    # её не отдаёт, это отдельный синк, см. vacation_days_sync_service) —
    # тогда run_sync не трогает уже сохранённое значение, а не сбрасывает
    # его на False при каждом запуске.
    has_benefits: bool | None = None
    is_active: bool = True
    # Табельный номер — если источник его отдаёт (см. app/integrations/
    # org_directory.py), сопоставление с другими интеграциями (учебные
    # планы, дни отпуска) настраивается сразу, без ручного ввода HR.
    employee_code: str | None = None
