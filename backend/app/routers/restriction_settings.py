from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import CurrentUser, DbSession, require_role
from app.models.user import User
from app.schemas.restriction_settings import RestrictionSettingsOut
from app.services import permissions, restriction_settings_service

router = APIRouter(prefix="/restriction-settings", tags=["restriction-settings"])

HrAdmin = Annotated[User, Depends(require_role(permissions.HR_ADMIN))]


class RestrictionSettingsUpdate(BaseModel):
    enabled: bool
    params: dict


@router.get("", response_model=list[RestrictionSettingsOut])
def list_restriction_settings(db: DbSession, _: CurrentUser) -> list[RestrictionSettingsOut]:
    """Read-only для всех — фронт использует значения (напр. min_days) вместо
    хардкода. Изменение (PUT) доступно только hr_admin."""
    return restriction_settings_service.get_all(db)


@router.put("/{key}", response_model=RestrictionSettingsOut)
def update_restriction_setting(
    key: str, body: RestrictionSettingsUpdate, db: DbSession, user: HrAdmin
) -> RestrictionSettingsOut:
    return restriction_settings_service.update(db, user, key, body.enabled, body.params)
