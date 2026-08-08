from datetime import date

from sqlalchemy.orm import Session

from app.models.restriction_settings import BLOCKED_PERIOD_ENFORCEMENT, RestrictionSettings
from app.models.user import User
from app.services import blocked_period_service
from app.services.validation.types import Violation

KEY = BLOCKED_PERIOD_ENFORCEMENT
EXEMPTABLE = True


def check(
    db: Session,
    settings_row: RestrictionSettings,
    user: User,
    date_from: date,
    date_to: date,
) -> Violation | None:
    blocks = blocked_period_service.get_effective_blocks(db, user, date_from, date_to)
    if not blocks:
        return None

    first = blocks[0]
    return Violation(
        code="BLOCKED_PERIOD_OVERLAP",
        message_ru=f"Период пересекается с недоступным периодом: {first.reason} "
        f"({first.date_from} — {first.date_to}).",
        params={
            "blocked_periods": [
                {"date_from": str(b.date_from), "date_to": str(b.date_to), "reason": b.reason}
                for b in blocks
            ]
        },
    )
