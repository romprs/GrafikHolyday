from datetime import date

import pytest

from app.core.exceptions import ValidationFailedError
from app.models.leave_balance import LeaveBalance
from app.models.leave_request import PENDING_APPROVAL
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


def test_adds_multiple_non_overlapping_drafts(db_session, setup):
    # Баланс 20: 7 + 13 = 20 — остаток после каждого добавления либо >= 7, либо 0.
    leave_request_service.create_draft(
        db_session, setup["user"], date(2026, 6, 1), date(2026, 6, 7), None
    )
    leave_request_service.create_draft(
        db_session, setup["user"], date(2026, 9, 1), date(2026, 9, 13), None
    )
    drafts = leave_request_service.list_drafts(db_session, setup["user"], 2026)
    assert len(drafts) == 2


def test_rejects_periods_overlapping_each_other(db_session, setup):
    leave_request_service.create_draft(
        db_session, setup["user"], date(2026, 6, 1), date(2026, 6, 10), None
    )
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, setup["user"], date(2026, 6, 8), date(2026, 6, 15), None
        )


def test_rejects_draft_exceeding_remaining_balance(db_session, setup):
    # Баланс 20: первый черновик выбирает весь остаток (остаток 0), второй уже не помещается.
    leave_request_service.create_draft(
        db_session, setup["user"], date(2026, 6, 1), date(2026, 6, 20), None
    )
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, setup["user"], date(2026, 9, 1), date(2026, 9, 7), None
        )


def test_failed_draft_does_not_affect_existing_drafts(db_session, setup):
    leave_request_service.create_draft(
        db_session, setup["user"], date(2026, 6, 1), date(2026, 6, 7), None
    )
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, setup["user"], date(2026, 6, 3), date(2026, 6, 9), None
        )
    drafts = leave_request_service.list_drafts(db_session, setup["user"], 2026)
    assert len(drafts) == 1


def test_rejects_short_draft(db_session, setup):
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, setup["user"], date(2026, 6, 1), date(2026, 6, 3), None
        )


def test_submit_rejects_partial_selection(db_session, setup):
    # Баланс 20, выбрано только 7 — отправлять нельзя, пока не выбран весь остаток.
    leave_request_service.create_draft(
        db_session, setup["user"], date(2026, 6, 1), date(2026, 6, 7), None
    )
    with pytest.raises(ValidationFailedError):
        leave_request_service.submit_drafts(db_session, setup["user"], 2026)


def test_submit_succeeds_on_exact_balance_match(db_session, setup):
    leave_request_service.create_draft(
        db_session, setup["user"], date(2026, 6, 1), date(2026, 6, 13), None
    )
    leave_request_service.create_draft(
        db_session, setup["user"], date(2026, 9, 1), date(2026, 9, 7), None
    )
    submitted = leave_request_service.submit_drafts(db_session, setup["user"], 2026)
    assert len(submitted) == 2
    assert all(r.status == PENDING_APPROVAL for r in submitted)
    assert leave_request_service.list_drafts(db_session, setup["user"], 2026) == []
