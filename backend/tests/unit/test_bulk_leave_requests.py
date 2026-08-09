from datetime import date

import pytest

from app.core.exceptions import ValidationFailedError
from app.models.leave_balance import LeaveBalance
from app.models.leave_type import LeaveType
from app.models.restriction_settings import (
    LEAVE_BALANCE_LIMIT,
    MIN_LEAVE_DURATION,
    OWN_OVERLAP_CHECK,
    RestrictionSettings,
)
from app.models.user import User
from app.services import leave_request_service


@pytest.fixture()
def setup(db_session):
    db_session.add(RestrictionSettings(key=MIN_LEAVE_DURATION, enabled=True, params={"min_days": 7}))
    db_session.add(RestrictionSettings(key=LEAVE_BALANCE_LIMIT, enabled=True, params={}))
    db_session.add(RestrictionSettings(key=OWN_OVERLAP_CHECK, enabled=True, params={}))
    db_session.add(LeaveType(code="vacation", name_ru="Отпуск"))
    db_session.flush()
    user = User(email="u@bulk.local", full_name="u")
    db_session.add(user)
    db_session.flush()
    db_session.add(LeaveBalance(user_id=user.id, year=2026, accrued_days=20))
    db_session.flush()
    return {"user": user}


def test_creates_multiple_non_overlapping_periods(db_session, setup):
    created = leave_request_service.create_and_submit_bulk(
        db_session,
        setup["user"],
        [
            (date(2026, 6, 1), date(2026, 6, 7), None),
            (date(2026, 9, 1), date(2026, 9, 7), None),
        ],
    )
    assert len(created) == 2


def test_rejects_periods_overlapping_each_other(db_session, setup):
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_and_submit_bulk(
            db_session,
            setup["user"],
            [
                (date(2026, 6, 1), date(2026, 6, 10), None),
                (date(2026, 6, 8), date(2026, 6, 15), None),
            ],
        )


def test_rejects_when_total_exceeds_balance(db_session, setup):
    # 14 + 7 = 21 > 20 доступных
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_and_submit_bulk(
            db_session,
            setup["user"],
            [
                (date(2026, 6, 1), date(2026, 6, 14), None),
                (date(2026, 9, 1), date(2026, 9, 7), None),
            ],
        )


def test_atomic_nothing_created_on_failure(db_session, setup):
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_and_submit_bulk(
            db_session,
            setup["user"],
            [
                (date(2026, 6, 1), date(2026, 6, 7), None),
                (date(2026, 6, 3), date(2026, 6, 9), None),
            ],
        )
    assert leave_request_service.list_own(db_session, setup["user"]) == []


def test_rejects_short_period_in_batch(db_session, setup):
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_and_submit_bulk(
            db_session,
            setup["user"],
            [(date(2026, 6, 1), date(2026, 6, 3), None)],
        )
