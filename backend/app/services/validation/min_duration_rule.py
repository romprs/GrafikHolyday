from datetime import date

from sqlalchemy.orm import Session

from app.models.restriction_settings import MIN_LEAVE_DURATION
from app.models.restriction_settings import RestrictionSettings
from app.models.user import User
from app.services.validation.types import Violation

KEY = MIN_LEAVE_DURATION
EXEMPTABLE = True


def check(
    db: Session,
    settings_row: RestrictionSettings,
    user: User,
    date_from: date,
    date_to: date,
) -> Violation | None:
    min_days = settings_row.params.get("min_days", 1)
    requested_days = (date_to - date_from).days + 1
    if requested_days < min_days:
        return Violation(
            code="MIN_DURATION_VIOLATION",
            message_ru=f"Минимальная длительность отпуска — {min_days} дн. (указано {requested_days}).",
            params={"min_days": min_days, "requested_days": requested_days},
        )
    return None
