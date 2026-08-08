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
def settings_enabled(db_session):
    db_session.add(RestrictionSettings(key=MIN_LEAVE_DURATION, enabled=True, params={"min_days": 1}))
    db_session.add(RestrictionSettings(key=BLOCKED_PERIOD_ENFORCEMENT, enabled=True, params={}))
    db_session.flush()


@pytest.fixture()
def hr(db_session):
    from app.models.user_role import UserRole

    user = User(email="hr@test.local", full_name="hr")
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role="hr_admin"))
    db_session.flush()
    return user


def test_overlapping_request_rejected(db_session, settings_enabled, hr):
    employee = User(email="e@test.local", full_name="e")
    db_session.add(employee)
    db_session.flush()

    blocked_period_service.create(
        db_session, hr, date(2026, 6, 1), date(2026, 6, 10), "Сборы", GLOBAL, None, None
    )

    violations = validate_leave_request(db_session, employee, date(2026, 6, 5), date(2026, 6, 6))
    assert any(v.code == "BLOCKED_PERIOD_OVERLAP" for v in violations)


def test_has_benefits_bypasses_blocked_period(db_session, settings_enabled, hr):
    employee = User(email="e2@test.local", full_name="e2", has_benefits=True)
    db_session.add(employee)
    db_session.flush()

    blocked_period_service.create(
        db_session, hr, date(2026, 6, 1), date(2026, 6, 10), "Сборы", GLOBAL, None, None
    )

    violations = validate_leave_request(db_session, employee, date(2026, 6, 5), date(2026, 6, 6))
    assert violations == []


def test_disabled_enforcement_allows_overlap(db_session, settings_enabled, hr):
    employee = User(email="e3@test.local", full_name="e3")
    db_session.add(employee)
    db_session.flush()

    blocked_period_service.create(
        db_session, hr, date(2026, 6, 1), date(2026, 6, 10), "Сборы", GLOBAL, None, None
    )
    setting = db_session.get(RestrictionSettings, BLOCKED_PERIOD_ENFORCEMENT)
    setting.enabled = False
    db_session.flush()

    violations = validate_leave_request(db_session, employee, date(2026, 6, 5), date(2026, 6, 6))
    assert violations == []
