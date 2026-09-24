from datetime import date

from pydantic import BaseModel


class StudyPeriodsTestIn(BaseModel):
    """Параметры подключения берутся прямо из формы (не обязательно уже
    сохранённые) — чтобы можно было проверить новый URL/логин до того, как
    его сохранять."""

    base_url: str
    auth_login: str
    auth_password: str
    verify_tls: bool = False
    employee_codes: list[str]
    period_from: date | None = None
    period_to: date | None = None


class StudyPeriodsTestResultOut(BaseModel):
    employee_code: str
    request_url: str
    http_status: int | None
    response_body_preview: str | None
    parsed_entries_count: int | None
    error: str | None
