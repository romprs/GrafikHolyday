"""Клиент источника оргструктуры (departments) — REST/OData эндпоинт вида
GetDepartments(), отдающий JSON с единственным строковым полем "value" —
не массив, а вручную склеенный список записей вида
    "<id>#<name>#<bossid>#<parentid>#<zgdid>|<id>#<name>#..."
(пример ответа и формат вставки в БД — от заказчика, см. PHP-скрипт в
описании задачи). "zgdid" (замгендиректора по направлению) в текущей
модели OrgUnit не хранится — здесь нет для него применения (нет
UI/фичи, завязанной на группировку по направлениям), можно добавить
отдельным полем позже, если понадобится.

Сотрудники (fetch_users) источником пока не предоставлены — GetDepartments()
даёт только оргструктуру. Возвращаем пустой список: синк подразделений и
иерархии работает уже сейчас, руководители (head_user_id) появятся, когда
будет согласован эндпоинт сотрудников.
"""

import httpx

from app.sync.dto import ExternalOrgUnitDTO, ExternalUserDTO
from app.sync.interface import ExternalDirectoryClient

SYSTEM_NAME = "org_directory_rest"


def _clean_ref(raw: str) -> str | None:
    value = raw.strip()
    return value if value and value != "0" else None


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


class OrgDirectoryClient(ExternalDirectoryClient):
    def __init__(
        self, departments_url: str, login: str, password: str, verify_tls: bool = True, timeout: float = 120.0
    ):
        self._departments_url = departments_url
        self._auth = httpx.BasicAuth(login, password)
        self._verify_tls = verify_tls
        self._timeout = timeout

    @property
    def system_name(self) -> str:
        return SYSTEM_NAME

    def fetch_org_units(self) -> list[ExternalOrgUnitDTO]:
        response = httpx.get(
            self._departments_url, auth=self._auth, verify=self._verify_tls, timeout=self._timeout
        )
        response.raise_for_status()
        return parse_departments(response.json()["value"])

    def fetch_users(self) -> list[ExternalUserDTO]:
        return []
