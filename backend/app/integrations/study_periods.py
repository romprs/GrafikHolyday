"""Клиент и парсер источника учебных планов (недоступные периоды сотрудников).

Режим "file" (весь файл разом, все сотрудники) отдаёт список блоков,
сгруппированных по табельному номеру:
    [{"<табельный номер>": [{"ПрограмаОбучения": "...", "Дата": "2027-01-01T00:00:00",
                              "КолВоЧасов": 16}, ...]}, ...]
— см. parse_entries.

Режим "http" (запрос по одному табельному номеру за раз) отдаёт ПЛОСКИЙ
список записей БЕЗ обёртки по табельному номеру — сам номер известен только
из контекста запроса (Employee в query), в ответе его нет:
    [{"ПрограмаОбучения": "...", "Дата": "2027-01-01T00:00:00", "КолВоЧасов": 16}, ...]
— см. parse_flat_entries. Формат подтверждён реальным ответом источника
(сентябрь 2026): ключ "ПрограмаОбучения" — с одной "м" (опечатка на стороне
источника), дата — ISO 8601, а не "24.10.2024 0:00:00", как предполагалось
изначально.
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
    raw = raw.strip()
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        pass
    return datetime.strptime(raw, "%d.%m.%Y %H:%M:%S").date()


def _program_name(item: dict) -> str:
    # "ПрограмаОбучения" (одна "м") — реальное написание ключа в ответе
    # источника; "ПрограммаОбучения" оставлено как fallback на случай
    # правки опечатки на их стороне или иного написания в режиме "file".
    if "ПрограмаОбучения" in item:
        return item["ПрограмаОбучения"]
    return item["ПрограммаОбучения"]


def _parse_item(employee_code: str, item: dict) -> StudyPeriodEntryDTO:
    return StudyPeriodEntryDTO(
        employee_code=str(employee_code),
        program_name=_program_name(item),
        date=_parse_date(item["Дата"]),
        hours=float(item.get("КолВоЧасов") or 0),
    )


def parse_entries(raw: list[dict]) -> list[StudyPeriodEntryDTO]:
    """Разбор ответа режима "file" — список блоков, сгруппированных по
    табельному номеру."""
    entries: list[StudyPeriodEntryDTO] = []
    for block in raw:
        if not isinstance(block, dict):
            continue
        for employee_code, programs in block.items():
            for item in programs or []:
                entries.append(_parse_item(employee_code, item))
    return entries


def parse_flat_entries(employee_code: str, raw: list[dict]) -> list[StudyPeriodEntryDTO]:
    """Разбор ответа режима "http" — плоский список записей одного
    сотрудника, без обёртки по табельному номеру (он известен из запроса)."""
    return [_parse_item(employee_code, item) for item in raw if isinstance(item, dict)]


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

    def test_fetch(self, employee_code: str, period_from: date, period_to: date) -> dict:
        """Как fetch_raw, но не бросает исключение, а возвращает разбор
        запроса/ответа целиком — для тестового подключения в админке
        (POST /admin/study-periods/test), где HR должен своими глазами
        увидеть, какой именно запрос ушёл и что реально ответил источник,
        а не только "синхронизация не прошла" из истории обычного синка."""
        params = {
            "type": "JSON",
            "Period1": f"{period_from:%d.%m.%Y} 0:00:00",
            "Period2": f"{period_to:%d.%m.%Y} 23:59:59",
            "Employee": employee_code,
        }
        request_url = str(httpx.Request("GET", self._base_url, params=params).url)
        result: dict = {
            "employee_code": employee_code,
            "request_url": request_url,
            "http_status": None,
            "response_body_preview": None,
            "parsed_entries_count": None,
            "error": None,
        }
        try:
            response = httpx.get(
                self._base_url,
                params=params,
                auth=self._auth,
                verify=self._verify_tls,
                timeout=self._timeout,
            )
        except httpx.RequestError as exc:
            result["error"] = f"Не удалось соединиться: {exc}"
            return result

        result["http_status"] = response.status_code
        result["response_body_preview"] = response.text[:1000]
        if response.is_error:
            result["error"] = f"Источник ответил HTTP {response.status_code}"
            return result

        try:
            data = response.json()
        except ValueError as exc:
            result["error"] = f"Ответ не является корректным JSON: {exc}"
            return result

        try:
            entries = parse_flat_entries(employee_code, data if isinstance(data, list) else [data])
            result["parsed_entries_count"] = len(entries)
        except Exception as exc:  # noqa: BLE001 — формат ответа не совпал с ожидаемым, это тоже полезно увидеть в тесте
            result["error"] = f"Ответ пришёл, но не разобран (формат не совпадает с ожидаемым): {exc}"
        return result
