"""Клиент и парсер источника учебных планов (недоступные периоды сотрудников).

Формат ответа предварительный (контракт с реальным источником согласован
частично) — список объектов вида
    [{"<табельный номер>": [{"ПрограммаОбучения": "...", "Дата": "24.10.2024 0:00:00",
                              "КолВоЧасов": "16"}, ...]}, ...]
Один и тот же parse_entries используется и для файла целиком (все
сотрудники разом, режим "file"), и для склеенных ответов HTTP-источника
(по одному сотруднику за раз, режим "http") — структура записи одинаковая.
"""

import logging
from datetime import date, datetime

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


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
        logger.info(
            "Запрос к источнику недоступных периодов (1С): GET %s, табельный номер=%s, период=%s..%s",
            self._base_url,
            employee_code,
            period_from,
            period_to,
        )
        try:
            response = httpx.get(
                self._base_url,
                params=params,
                auth=self._auth,
                verify=self._verify_tls,
                timeout=self._timeout,
            )
        except httpx.RequestError as exc:
            logger.error(
                "Не удалось соединиться с источником недоступных периодов (%s, табельный номер=%s): %s",
                self._base_url,
                employee_code,
                exc,
            )
            raise RuntimeError(f"Не удалось соединиться с {self._base_url}: {exc}") from exc

        logger.info(
            "Ответ от источника недоступных периодов (табельный номер=%s): HTTP %s, %d байт",
            employee_code,
            response.status_code,
            len(response.content),
        )
        if response.is_error:
            body_preview = response.text[:500]
            logger.error(
                "Источник недоступных периодов вернул ошибку: GET %s (табельный номер=%s) -> HTTP %s. Тело ответа: %s",
                self._base_url,
                employee_code,
                response.status_code,
                body_preview,
            )
            raise RuntimeError(
                f"Источник ответил HTTP {response.status_code} на запрос по табельному номеру {employee_code}"
                + (f": {body_preview}" if body_preview else "")
            )

        try:
            data = response.json()
        except ValueError as exc:
            body_preview = response.text[:500]
            logger.error(
                "Не удалось разобрать ответ источника недоступных периодов (табельный номер=%s) как JSON: %s. Тело ответа (начало): %s",
                employee_code,
                exc,
                body_preview,
            )
            raise RuntimeError(
                f"Ответ источника (табельный номер={employee_code}) не является корректным JSON: {exc}"
            ) from exc
        return data if isinstance(data, list) else [data]
