from datetime import date

from sqlalchemy.orm import Session

from app.models.restriction_settings import LEAVE_BALANCE_LIMIT, RestrictionSettings
from app.models.user import User
from app.services import leave_balance_service
from app.services.validation.types import Violation

KEY = LEAVE_BALANCE_LIMIT
EXEMPTABLE = True


def check(
    db: Session,
    settings_row: RestrictionSettings,
    user: User,
    date_from: date,
    date_to: date,
) -> Violation | None:
    """Остаток считается по году даты начала отпуска — упрощение для случаев,
    когда период переходит через границу года (редкий случай для MVP)."""
    requested_days = (date_to - date_from).days + 1
    remaining = leave_balance_service.get_remaining_for_new_request(db, user, date_from.year)

    if requested_days > remaining:
        return Violation(
            code="LEAVE_BALANCE_EXCEEDED",
            message_ru=f"Запрошено {requested_days} дн., доступно {remaining} дн. "
            f"на {date_from.year} год.",
            params={"requested_days": requested_days, "remaining_days": remaining},
        )
    return None
