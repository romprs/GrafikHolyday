"""Клиент источника остатка дней отпуска и признака льготника —
GetVacationDaysCount?tn=<табельный номер>, отдельный запрос на каждого
сотрудника (другая система, чем оргструктура/сотрудники — HRM, не DRX).

Ответ — JSON-массив из одного объекта:
    [{"Employee": "...", "Podr": "...", "Position": "...",
      "DaysCount": 36, "L": "Нет", "Kat": "Специалисты",
      "HireDate": "01.09.2027", "DismissalDate": null}]
"L" — льготник ("Да"/"Нет"). "Kat"/"Position"/"Podr"/"Employee" в текущей
модели не хранятся — нет для них применения (только счёт дней и льгота).

"HireDate"/"DismissalDate" — дата приёма/увольнения, ожидаемый КОНТРАКТ
(источник ещё не отдаёт эти поля на момент написания, добавляются на
стороне 1С). "DismissalDate" — null/отсутствует/пустая строка, пока
сотрудник работает. Формат даты — как в остальных полях этого источника,
"ДД.ММ.ГГГГ"; на всякий случай (см. историю с датами study_periods —
Phase 6.33, где реальный формат разошёлся с ожидаемым) парсер по формату
даты не строгий: сначала пробует ISO 8601, затем "ДД.ММ.ГГГГ"."""

import logging
from datetime import date, datetime

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

SYSTEM_NAME = "vacation_days_rest"


class VacationDaysEntryDTO(BaseModel):
    days_count: float
    is_beneficiary: bool
    hire_date: date | None = None
    termination_date: date | None = None


def _parse_optional_date(raw: object) -> date | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    return datetime.strptime(text, "%d.%m.%Y").date()


def parse_vacation_days(raw: list[dict]) -> VacationDaysEntryDTO | None:
    if not raw or not isinstance(raw[0], dict) or "DaysCount" not in raw[0]:
        return None
    item = raw[0]
    return VacationDaysEntryDTO(
        days_count=float(item["DaysCount"]),
        is_beneficiary=str(item.get("L", "")).strip().lower() == "да",
        hire_date=_parse_optional_date(item.get("HireDate")),
        termination_date=_parse_optional_date(item.get("DismissalDate")),
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
        try:
            response = httpx.get(
                self._base_url,
                params={"tn": tabnum},
                auth=self._auth,
                verify=self._verify_tls,
                timeout=self._timeout,
            )
        except httpx.RequestError as exc:
            logger.error(
                "Не удалось соединиться с источником дней отпуска (%s, табельный номер=%s): %s",
                self._base_url,
                tabnum,
                exc,
            )
            raise

        if response.is_error:
            # Тело ответа сюда не попадает через str(exc) у HTTPStatusError
            # (только код и URL) — а именно оно нужно, чтобы было что
            # показать стороне 1С при эскалации сбоя на их сервисе.
            body_preview = response.text[:500]
            logger.error(
                "Источник дней отпуска вернул ошибку: GET %s (табельный номер=%s) -> HTTP %s. "
                "Тело ответа: %s",
                self._base_url,
                tabnum,
                response.status_code,
                body_preview,
            )
        response.raise_for_status()
        return parse_vacation_days(response.json())
