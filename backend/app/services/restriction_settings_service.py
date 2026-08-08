from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.restriction_settings import RestrictionSettings
from app.models.user import User


def get(db: Session, key: str) -> RestrictionSettings | None:
    return db.scalar(select(RestrictionSettings).where(RestrictionSettings.key == key))


def get_all(db: Session) -> list[RestrictionSettings]:
    return list(db.scalars(select(RestrictionSettings).order_by(RestrictionSettings.key)).all())


def update(
    db: Session, actor: User, key: str, enabled: bool, params: dict
) -> RestrictionSettings:
    setting = get(db, key)
    if setting is None:
        raise NotFoundError("Настройка не найдена", {"key": key})

    setting.enabled = enabled
    setting.params = params
    setting.updated_by = actor.id
    db.commit()
    db.refresh(setting)
    return setting
