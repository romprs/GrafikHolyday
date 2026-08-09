from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.restriction_settings import PLANNING_YEAR, RestrictionSettings
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


def get_planning_year(db: Session) -> int:
    """Год, на который сейчас ведётся планирование отпусков — фиксируется HR
    в настройках. Если не задан явно, используется текущий календарный год."""
    setting = get(db, PLANNING_YEAR)
    if setting is None:
        return date.today().year
    return int(setting.params.get("year", date.today().year))
