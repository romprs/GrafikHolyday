from datetime import date

from sqlalchemy.orm import Session

from app.models.restriction_settings import (
    LEAVE_BALANCE_LIMIT,
    MIN_LEAVE_DURATION,
    RestrictionSettings,
)
from app.models.user import User
from app.services import leave_balance_service, restriction_settings_service
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

    # Остаток после этого периода не должен "застревать" между 1 днём и
    # минимальной длительностью — такой остаток нельзя ни использовать
    # отдельным периодом, ни отправить (submit_drafts требует точного 0).
    leftover = remaining - requested_days
    if leftover > 0:
        min_duration_setting = restriction_settings_service.get(db, MIN_LEAVE_DURATION)
        if min_duration_setting is not None and min_duration_setting.enabled:
            min_days = min_duration_setting.params.get("min_days", 1)
            if leftover < min_days:
                return Violation(
                    code="LEAVE_BALANCE_STRANDED_REMAINDER",
                    message_ru=(
                        f"После этого периода останется {leftover} дн. остатка — этого "
                        f"недостаточно для отдельного отпуска (минимум {min_days} дн.) и "
                        f"такой остаток нельзя будет использовать. Измените длительность "
                        f"периода так, чтобы остаток стал равен 0 либо не менее {min_days} дн."
                    ),
                    params={"leftover_days": leftover, "min_days": min_days},
                )
    return None
