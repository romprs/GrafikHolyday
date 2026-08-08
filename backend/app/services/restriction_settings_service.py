from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.restriction_settings import RestrictionSettings


def get(db: Session, key: str) -> RestrictionSettings | None:
    return db.scalar(select(RestrictionSettings).where(RestrictionSettings.key == key))


def get_all(db: Session) -> list[RestrictionSettings]:
    return list(db.scalars(select(RestrictionSettings).order_by(RestrictionSettings.key)).all())
