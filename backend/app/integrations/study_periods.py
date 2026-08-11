"""Клиент и парсер источника учебных планов (недоступные периоды сотрудников).

Формат ответа предварительный (контракт с реальным источником согласован
частично) — список объектов вида
    [{"<табельный номер>": [{"ПрограммаОбучения": "...", "Дата": "24.10.2024 0:00:00",
                              "КолВоЧасов": "16"}, ...]}, ...]
Один и тот же parse_entries используется и для файла целиком (все
сотрудники разом, режим "file"), и для склеенных ответов HTTP-источника
(по одному сотруднику за раз, режим "http") — структура записи одинаковая.
"""

from datetime import date, datetime

import httpx
from pydantic import BaseModel


class StudyPeriodEntryDTO(BaseModel):
    employee_code: str
    program_name: str
    date: date
    hours: float


def _parse_date(raw: str) -> date:
    return datetime.strptime(raw.strip(), "%d.%m.%Y %H:%M:%S").date()


def parse_entries(raw: list[dict]) -> list[StudyPeriodEntryDTO]:
    entries: list[StudyPeriodEntryDTO] = []
    for block in raw:
        if not isinstance(block, dict):
            continue
        for employee_code, programs in block.items():
            for item in programs or []:
                entries.append(
                    StudyPeriodEntryDTO(
                        employee_code=str(employee_code),
                        program_name=item["ПрограммаОбучения"],
                        date=_parse_date(item["Дата"]),
                        hours=float(item.get("КолВоЧасов") or 0),
                    )
                )
    return entries


class StudyPeriodsClient:
    """Одна заявка на сотрудника — контракт источника отдаёт план по одному
    табельному номеру за раз (см. Employee в query-параметрах)."""

    def __init__(
        self, base_url: str, login: str, password: str, verify_tls: bool = True, timeout: float = 60.0
    ):
        self._base_url = base_url.rstrip("/")
        self._auth = httpx.BasicAuth(login, password)
        self._verify_tls = verify_tls
        self._timeout = timeout

    def fetch_raw(self, employee_code: str, period_from: date, period_to: date) -> list[dict]:
        params = {
            "type": "JSON",
            "Period1": f"{period_from:%d.%m.%Y} 0:00:00",
            "Period2": f"{period_to:%d.%m.%Y} 23:59:59",
            "Employee": employee_code,
        }
        response = httpx.get(
            self._base_url,
            params=params,
            auth=self._auth,
            verify=self._verify_tls,
            timeout=self._timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else [data]
