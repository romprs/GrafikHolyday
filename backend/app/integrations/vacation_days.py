"""Клиент источника остатка дней отпуска и признака льготника —
GetVacationDaysCount?tn=<табельный номер>, отдельный запрос на каждого
сотрудника (другая система, чем оргструктура/сотрудники — HRM, не DRX).

Ответ — JSON-массив из одного объекта:
    [{"Employee": "...", "Podr": "...", "Position": "...",
      "DaysCount": 36, "L": "Нет", "Kat": "Специалисты"}]
"L" — льготник ("Да"/"Нет"). "Kat"/"Position"/"Podr"/"Employee" в текущей
модели не хранятся — нет для них применения (только счёт дней и льгота).
"""

import httpx
from pydantic import BaseModel

SYSTEM_NAME = "vacation_days_rest"


class VacationDaysEntryDTO(BaseModel):
    days_count: float
    is_beneficiary: bool


def parse_vacation_days(raw: list[dict]) -> VacationDaysEntryDTO | None:
    if not raw or not isinstance(raw[0], dict) or "DaysCount" not in raw[0]:
        return None
    item = raw[0]
    return VacationDaysEntryDTO(
        days_count=float(item["DaysCount"]),
        is_beneficiary=str(item.get("L", "")).strip().lower() == "да",
    )


class VacationDaysClient:
    def __init__(
        self, base_url: str, login: str, password: str, verify_tls: bool = True, timeout: float = 60.0
    ):
        self._base_url = base_url.rstrip("/")
        self._auth = httpx.BasicAuth(login, password)
        self._verify_tls = verify_tls
        self._timeout = timeout

    def fetch(self, tabnum: str) -> VacationDaysEntryDTO | None:
        response = httpx.get(
            self._base_url,
            params={"tn": tabnum},
            auth=self._auth,
            verify=self._verify_tls,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return parse_vacation_days(response.json())
