"""Заглушка под реальный REST API внешней корпоративной системы.

Контракт (эндпоинты, аутентификация, формат ответа) пока не известен —
подключается в Phase 5+ реализацией fetch_org_units/fetch_users поверх
httpx-клиента, без изменений в sync_service.py (тот работает через
ExternalDirectoryClient и не завязан на конкретного вендора).
"""

from app.sync.dto import ExternalOrgUnitDTO, ExternalUserDTO
from app.sync.interface import ExternalDirectoryClient


class RestDirectoryClient(ExternalDirectoryClient):
    def __init__(self, base_url: str, api_token: str):
        self._base_url = base_url
        self._api_token = api_token

    @property
    def system_name(self) -> str:
        return "corporate_directory"

    def fetch_org_units(self) -> list[ExternalOrgUnitDTO]:
        raise NotImplementedError("Контракт внешнего API ещё не согласован")

    def fetch_users(self) -> list[ExternalUserDTO]:
        raise NotImplementedError("Контракт внешнего API ещё не согласован")
