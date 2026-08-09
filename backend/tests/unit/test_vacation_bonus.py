from datetime import date

import pytest

from app.core.exceptions import ValidationFailedError
from app.models.leave_balance import LeaveBalance
from app.models.leave_type import LeaveType
from app.models.restriction_settings import VACATION_BONUS, RestrictionSettings
from app.models.user import User
from app.services import leave_request_service


@pytest.fixture()
def employee(db_session):
    lt = LeaveType(code="vacation", name_ru="Отпуск")
    db_session.add(lt)
    user = User(email="bonus@test.local", full_name="Bonus")
    db_session.add(user)
    db_session.flush()
    db_session.add(LeaveBalance(user_id=user.id, year=2026, accrued_days=20))
    db_session.flush()
    return user


@pytest.fixture()
def bonus_setting(db_session):
    setting = RestrictionSettings(key=VACATION_BONUS, enabled=True, params={"min_days": 14})
    db_session.add(setting)
    db_session.flush()
    return setting


def test_bonus_requested_for_long_period_succeeds(db_session, employee, bonus_setting):
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 6, 1), date(2026, 6, 20), None, bonus_requested=True
    )
    assert request.bonus_requested is True


def test_bonus_requested_for_short_period_rejected(db_session, employee, bonus_setting):
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, employee, date(2026, 6, 1), date(2026, 6, 10), None, bonus_requested=True
        )


def test_bonus_requested_exactly_at_threshold_rejected(db_session, employee, bonus_setting):
    # "более 14" — ровно 14 не считается, порог строго больше
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, employee, date(2026, 6, 1), date(2026, 6, 14), None, bonus_requested=True
        )


def test_bonus_requested_when_program_disabled_rejected(db_session, employee):
    db_session.add(RestrictionSettings(key=VACATION_BONUS, enabled=False, params={"min_days": 14}))
    db_session.flush()
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, employee, date(2026, 6, 1), date(2026, 6, 20), None, bonus_requested=True
        )


def test_no_bonus_requested_does_not_check_threshold(db_session, employee, bonus_setting):
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 6, 1), date(2026, 6, 5), None, bonus_requested=False
    )
    assert request.bonus_requested is False
