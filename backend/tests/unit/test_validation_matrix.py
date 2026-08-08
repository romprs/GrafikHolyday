from datetime import date

import pytest

from app.models.blocked_period import GLOBAL
from app.models.restriction_settings import (
    BLOCKED_PERIOD_ENFORCEMENT,
    MIN_LEAVE_DURATION,
    RestrictionSettings,
)
from app.models.user import User
from app.services import blocked_period_service
from app.services.validation.engine import validate_leave_request


@pytest.fixture()
def hr(db_session):
    from app.models.user_role import UserRole

    user = User(email="hr@matrix.local", full_name="hr")
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role="hr_admin"))
    db_session.flush()
    return user


@pytest.mark.parametrize(
    "min_duration_enabled,has_benefits,requested_days,expect_violation",
    [
        (True, False, 3, True),  # правило включено, обычный сотрудник, нарушает -> блок
        (True, False, 10, False),  # включено, не нарушает -> ок
        (True, True, 3, False),  # включено, но льготник -> обход
        (False, False, 3, False),  # выключено -> не проверяется вовсе
    ],
)
def test_min_duration_matrix(
    db_session, min_duration_enabled, has_benefits, requested_days, expect_violation
):
    db_session.add(
        RestrictionSettings(
            key=MIN_LEAVE_DURATION, enabled=min_duration_enabled, params={"min_days": 7}
        )
    )
    user = User(email="u@matrix.local", full_name="u", has_benefits=has_benefits)
    db_session.add(user)
    db_session.flush()

    violations = validate_leave_request(
        db_session, user, date(2026, 6, 1), date(2026, 6, requested_days)
    )
    has_violation = any(v.code == "MIN_DURATION_VIOLATION" for v in violations)
    assert has_violation == expect_violation


@pytest.mark.parametrize(
    "enforcement_enabled,has_benefits,overlaps_block,expect_violation",
    [
        (True, False, True, True),  # включено, обычный, пересекается -> блок
        (True, False, False, False),  # включено, не пересекается -> ок
        (True, True, True, False),  # включено, но льготник -> обход
        (False, False, True, False),  # выключено -> не проверяется
    ],
)
def test_blocked_period_matrix(
    db_session, hr, enforcement_enabled, has_benefits, overlaps_block, expect_violation
):
    db_session.add(
        RestrictionSettings(key=BLOCKED_PERIOD_ENFORCEMENT, enabled=enforcement_enabled, params={})
    )
    db_session.add(
        RestrictionSettings(key=MIN_LEAVE_DURATION, enabled=False, params={"min_days": 1})
    )
    db_session.flush()

    blocked_period_service.create(
        db_session, hr, date(2026, 6, 1), date(2026, 6, 10), "Сборы", GLOBAL, None, None
    )

    user = User(email="u2@matrix.local", full_name="u2", has_benefits=has_benefits)
    db_session.add(user)
    db_session.flush()

    request_range = (
        (date(2026, 6, 5), date(2026, 6, 6))
        if overlaps_block
        else (date(2026, 6, 20), date(2026, 6, 21))
    )
    violations = validate_leave_request(db_session, user, *request_range)
    has_violation = any(v.code == "BLOCKED_PERIOD_OVERLAP" for v in violations)
    assert has_violation == expect_violation
