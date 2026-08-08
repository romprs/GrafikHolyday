from datetime import date

from sqlalchemy.orm import Session

from app.models.user import User
from app.services import restriction_settings_service
from app.services.validation import min_duration_rule
from app.services.validation.types import Violation

# Порядок важен только для порядка сообщений в ответе — на логику не влияет.
_RULES = (min_duration_rule,)


def validate_leave_request(
    db: Session, user: User, date_from: date, date_to: date
) -> list[Violation]:
    """Прогоняет включённые правила. Льготники (has_benefits) пропускают все
    exemptable-правила одним флагом — единая точка исключения, а не per-rule логика.
    """
    skip_exemptable = user.has_benefits
    violations: list[Violation] = []

    for rule in _RULES:
        if rule.EXEMPTABLE and skip_exemptable:
            continue
        settings_row = restriction_settings_service.get(db, rule.KEY)
        if settings_row is None or not settings_row.enabled:
            continue
        violation = rule.check(db, settings_row, user, date_from, date_to)
        if violation is not None:
            violations.append(violation)

    return violations
