"""Клиент источника оргструктуры — REST/OData эндпоинты вида GetDepartments()
и GetEmployeers(), оба отдают JSON с единственным строковым полем "value" —
не массив, а вручную склеенный список записей вида "<f0>#<f1>#...|<f0>#...".
Пример ответа и формат вставки в БД — от заказчика, см. PHP-скрипты в
описании задачи.

"zgdid" (замгендиректора по направлению, из GetDepartments) в текущей
модели OrgUnit не хранится — здесь нет для него применения (нет UI/фичи,
завязанной на группировку по направлениям), можно добавить отдельным
полем позже, если понадобится.

Дни отпуска и признак льготника источник отдаёт отдельным запросом на
каждого сотрудника (GetVacationDaysCount) — это отдельная интеграция, см.
app/integrations/vacation_days.py и app/services/vacation_days_sync_service.py.
"""

import json
import logging
import re

import httpx

from app.sync.dto import ExternalOrgUnitDTO, ExternalUserDTO
from app.sync.interface import ExternalDirectoryClient

logger = logging.getLogger(__name__)

SYSTEM_NAME = "org_directory_rest"

_NUMERIC_CODE = re.compile(r"\d+")


def _clean_ref(raw: str) -> str | None:
    value = raw.strip()
    return value if value and value != "0" else None


def _clean_employee_code(raw: str) -> str | None:
    """В реальных данных табельный номер не всегда номер — часть записей
    заполнена служебными плейсхолдерами вида "б/н"/"БН"/"н/б" (без номера)
    или техническими метками ("int1c", "1C-01"): десятки разных написаний
    одного и того же "номера нет", которые при буквальном использовании
    столкнутся друг с другом (employee_code уникален). Табельный номер
    везде, где он реальный, — просто цифры, поэтому берём только такие."""
    value = raw.strip()
    return value if _NUMERIC_CODE.fullmatch(value) else None


def parse_departments(value: str) -> list[ExternalOrgUnitDTO]:
    dtos: list[ExternalOrgUnitDTO] = []
    for chunk in value.split("|"):
        chunk = chunk.strip()
        if not chunk:
            continue
        fields = chunk.split("#")
        if len(fields) < 4:
            continue  # неполная/битая запись — пропускаем, не роняя весь синк
        external_id, name, boss_id, parent_id = fields[0].strip(), fields[1].strip(), fields[2], fields[3]
        dtos.append(
            ExternalOrgUnitDTO(
                external_id=external_id,
                name=name,
                # Источник не отдаёт тип юнита (управление/отдел/цех/...) —
                # можно было бы угадывать по первому слову названия, но это
                # хрупко и не проверено на реальных данных; оставляем None.
                unit_kind=None,
                parent_external_id=_clean_ref(parent_id),
                head_external_id=_clean_ref(boss_id),
            )
        )
    return dtos


def parse_employees(value: str) -> list[ExternalUserDTO]:
    """Запись: "<id>#<fio>#<tabnum>#<podrid>#<login>". login — логин
    доменной учётки (обычно формата UPN), по нему предполагается
    авторизация в АРМ; у части сотрудников он ещё не заведён (пустой) —
    таких пропускаем, для User.email нужно непустое уникальное значение,
    появятся в системе, как только источник назначит им учётку."""
    dtos: list[ExternalUserDTO] = []
    for chunk in value.split("|"):
        chunk = chunk.strip()
        if not chunk:
            continue
        fields = chunk.split("#")
        if len(fields) < 5:
            continue
        external_id, fio, tabnum, podr_id, login = (f.strip() for f in fields[:5])
        if not external_id or not fio or not login:
            continue
        dtos.append(
            ExternalUserDTO(
                external_id=external_id,
                email=login.lower(),
                full_name=fio,
                org_unit_external_id=_clean_ref(podr_id),
                employee_code=_clean_employee_code(tabnum),
            )
        )
    return dtos


def extract_value(raw_text: str) -> str:
    """Достаёт поле "value" из сырого ответа источника. Помимо чистого
    JSON-ответа принимает и лог-файл вида "<url>{...json...}" (реальная
    выгрузка запроса+ответа, как она обычно и сохраняется вручную) —
    если текст целиком не парсится как JSON, берём его с первой '{'."""
    text = raw_text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        brace = text.find("{")
        if brace == -1:
            raise ValueError("Файл не является корректным JSON-ответом источника") from None
        try:
            data = json.loads(text[brace:])
        except json.JSONDecodeError as exc:
            raise ValueError("Файл не является корректным JSON-ответом источника") from exc
    value = data.get("value") if isinstance(data, dict) else None
    if not isinstance(value, str):
        raise ValueError('В файле нет строкового поля "value" — это не ответ источника')
    return value


class FileDirectoryClient(ExternalDirectoryClient):
    """Тот же источник (drx), что и OrgDirectoryClient, но данные приходят
    файлом (выгрузка/лог ответа), а не HTTP-запросом к работающему
    источнику. system_name намеренно тот же, что у OrgDirectoryClient —
    это разные способы доставки одних и тех же external_id, а не разные
    источники: повторный HTTP-синк после файлового импорта (и наоборот)
    должен обновлять те же записи, а не заводить дубли."""

    def __init__(
        self,
        org_units: list[ExternalOrgUnitDTO] | None = None,
        users: list[ExternalUserDTO] | None = None,
    ):
        self._org_units = org_units or []
        self._users = users or []

    @property
    def system_name(self) -> str:
        return SYSTEM_NAME

    def fetch_org_units(self) -> list[ExternalOrgUnitDTO]:
        return self._org_units

    def fetch_users(self) -> list[ExternalUserDTO]:
        return self._users


class OrgDirectoryClient(ExternalDirectoryClient):
    def __init__(
        self,
        departments_url: str,
        login: str,
        password: str,
        employees_url: str | None = None,
        verify_tls: bool = True,
        timeout: float = 120.0,
    ):
        self._departments_url = departments_url
        self._employees_url = employees_url
        self._auth = httpx.BasicAuth(login, password)
        self._verify_tls = verify_tls
        self._timeout = timeout

    @property
    def system_name(self) -> str:
        return SYSTEM_NAME

    def _fetch_value(self, url: str) -> str:
        logger.info("Запрос к источнику оргструктуры: GET %s", url)
        try:
            response = httpx.get(url, auth=self._auth, verify=self._verify_tls, timeout=self._timeout)
        except httpx.RequestError as exc:
            logger.error("Не удалось соединиться с %s: %s", url, exc)
            raise RuntimeError(f"Не удалось соединиться с {url}: {exc}") from exc

        logger.info("Ответ от %s: HTTP %s, %d байт", url, response.status_code, len(response.content))
        if response.is_error:
            body_preview = response.text[:500]
            logger.error(
                "Источник оргструктуры вернул ошибку: GET %s -> HTTP %s. Тело ответа: %s",
                url,
                response.status_code,
                body_preview,
            )
            raise RuntimeError(
                f"Источник ответил HTTP {response.status_code} на {url}"
                + (f": {body_preview}" if body_preview else "")
            )

        try:
            return extract_value(response.text)
        except ValueError as exc:
            logger.error(
                "Не удалось разобрать ответ источника (%s): %s. Тело ответа (начало): %s",
                url,
                exc,
                response.text[:500],
            )
            raise

    def fetch_org_units(self) -> list[ExternalOrgUnitDTO]:
        return parse_departments(self._fetch_value(self._departments_url))

    def fetch_users(self) -> list[ExternalUserDTO]:
        if not self._employees_url:
            return []
        return parse_employees(self._fetch_value(self._employees_url))
