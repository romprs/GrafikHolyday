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

import re

import httpx

from app.sync.dto import ExternalOrgUnitDTO, ExternalUserDTO
from app.sync.interface import ExternalDirectoryClient

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
        response = httpx.get(url, auth=self._auth, verify=self._verify_tls, timeout=self._timeout)
        response.raise_for_status()
        return response.json()["value"]

    def fetch_org_units(self) -> list[ExternalOrgUnitDTO]:
        return parse_departments(self._fetch_value(self._departments_url))

    def fetch_users(self) -> list[ExternalUserDTO]:
        if not self._employees_url:
            return []
        return parse_employees(self._fetch_value(self._employees_url))
