from fastapi import APIRouter

from app.dependencies import CurrentUser, DbSession
from app.schemas.restriction_settings import RestrictionSettingsOut
from app.services import restriction_settings_service

router = APIRouter(prefix="/restriction-settings", tags=["restriction-settings"])


@router.get("", response_model=list[RestrictionSettingsOut])
def list_restriction_settings(db: DbSession, _: CurrentUser) -> list[RestrictionSettingsOut]:
    """Read-only на этом этапе — фронт использует значения (напр. min_days) вместо
    хардкода. Управление (PUT, вкл/выкл) добавляется в Phase 4."""
    return restriction_settings_service.get_all(db)
