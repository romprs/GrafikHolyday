from abc import ABC, abstractmethod

from app.sync.dto import ExternalOrgUnitDTO, ExternalUserDTO


class ExternalDirectoryClient(ABC):
    """Граница между приложением и внешней корпоративной системой.

    Конкретная реализация (REST API конкретного вендора) неизвестна на этом
    этапе — за этим интерфейсом позже встанет rest_client.py без изменений
    в sync_service.py и остальном приложении.
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
