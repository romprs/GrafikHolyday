from datetime import date

import pytest

from app.models.restriction_settings import MIN_LEAVE_DURATION, RestrictionSettings
from app.models.user import User
from app.services.validation.engine import validate_leave_request


@pytest.fixture()
def min_duration_setting(db_session):
    setting = RestrictionSettings(
        key=MIN_LEAVE_DURATION, enabled=True, params={"min_days": 7}
    )
    db_session.add(setting)
    db_session.flush()
    return setting


def _make_user(has_benefits: bool = False) -> User:
    return User(email="u@test.local", full_name="u", has_benefits=has_benefits)


@pytest.mark.parametrize(
    "days,should_violate",
    [(6, True), (7, False), (8, False)],
)
def test_min_duration_boundary(db_session, min_duration_setting, days, should_violate):
    user = _make_user()
    db_session.add(user)
    db_session.flush()

    date_from = date(2026, 6, 1)
    date_to = date(2026, 6, 1 + days - 1)

    violations = validate_leave_request(db_session, user, date_from, date_to)
    assert bool(violations) == should_violate
    if should_violate:
        assert violations[0].code == "MIN_DURATION_VIOLATION"


def test_min_duration_disabled_no_violation(db_session, min_duration_setting):
    min_duration_setting.enabled = False
    db_session.flush()

    user = _make_user()
    db_session.add(user)
    db_session.flush()

    violations = validate_leave_request(db_session, user, date(2026, 6, 1), date(2026, 6, 2))
    assert violations == []


def test_has_benefits_bypasses_min_duration(db_session, min_duration_setting):
    user = _make_user(has_benefits=True)
    db_session.add(user)
    db_session.flush()

    violations = validate_leave_request(db_session, user, date(2026, 6, 1), date(2026, 6, 2))
    assert violations == []
