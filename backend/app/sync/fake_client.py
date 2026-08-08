import json
from pathlib import Path

from app.sync.dto import ExternalOrgUnitDTO, ExternalUserDTO
from app.sync.interface import ExternalDirectoryClient

DEFAULT_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "dev_directory.json"


class FakeDirectoryClient(ExternalDirectoryClient):
    """Читает статическую JSON-фикстуру — заглушка внешней системы для
    разработки и демо, пока контракт реального REST API не согласован."""

    def __init__(self, fixture_path: Path = DEFAULT_FIXTURE_PATH):
        self._fixture_path = fixture_path

    @property
    def system_name(self) -> str:
        return "dev_directory_fixture"

    def _load(self) -> dict:
        with open(self._fixture_path, encoding="utf-8") as f:
            return json.load(f)

    def fetch_org_units(self) -> list[ExternalOrgUnitDTO]:
        data = self._load()
        return [ExternalOrgUnitDTO(**ou) for ou in data["org_units"]]

    def fetch_users(self) -> list[ExternalUserDTO]:
        data = self._load()
        return [ExternalUserDTO(**u) for u in data["users"]]
