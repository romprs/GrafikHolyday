from abc import ABC, abstractmethod

from app.sync.dto import ExternalOrgUnitDTO, ExternalUserDTO


class ExternalDirectoryClient(ABC):
    """Граница между приложением и внешней корпоративной системой.

    Реализации: FakeDirectoryClient (тестовая фикстура) и
    app/integrations/org_directory.OrgDirectoryClient (реальный источник,
    отделы; сотрудников источник пока не отдаёт) — sync_service.py работает
    через этот интерфейс и не завязан на конкретную реализацию.
    """

    @property
    @abstractmethod
    def system_name(self) -> str:
        """Идентификатор источника — используется как external_system в маппинге."""
        raise NotImplementedError

    @abstractmethod
    def fetch_org_units(self) -> list[ExternalOrgUnitDTO]:
        raise NotImplementedError

    @abstractmethod
    def fetch_users(self) -> list[ExternalUserDTO]:
        raise NotImplementedError
