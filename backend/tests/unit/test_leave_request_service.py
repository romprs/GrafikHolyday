from datetime import date

import pytest

from app.core.exceptions import ForbiddenError, ValidationFailedError
from app.models.leave_balance import LeaveBalance
from app.models.leave_request import (
    APPROVED,
    CANCELLED,
    DRAFT,
    PENDING_APPROVAL,
    REJECTED,
)
from app.models.leave_type import LeaveType
from app.models.restriction_settings import MIN_LEAVE_DURATION, RestrictionSettings
from app.models.user import User
from app.services import leave_request_service


@pytest.fixture()
def vacation_type(db_session):
    lt = LeaveType(code="vacation", name_ru="Отпуск")
    db_session.add(lt)
    db_session.flush()
    return lt


@pytest.fixture()
def min_duration_setting(db_session):
    setting = RestrictionSettings(key=MIN_LEAVE_DURATION, enabled=True, params={"min_days": 7})
    db_session.add(setting)
    db_session.flush()
    return setting


@pytest.fixture()
def employee(db_session):
    user = User(email="employee@test.local", full_name="Employee")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture()
def balance_7(db_session, employee):
    db_session.add(LeaveBalance(user_id=employee.id, year=2026, accrued_days=7))
    db_session.flush()
    return employee


def submit_one(db_session, employee, date_from, date_to, comment=None):
    leave_request_service.create_draft(db_session, employee, date_from, date_to, comment)
    return leave_request_service.submit_drafts(db_session, employee, 2026)[0]


def test_create_draft_raises_on_violation(db_session, vacation_type, min_duration_setting, employee):
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, employee, date(2026, 6, 1), date(2026, 6, 3), None
        )


def test_create_draft_success(db_session, vacation_type, min_duration_setting, employee):
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 6, 1), date(2026, 6, 7), "отпуск"
    )
    assert request.status == DRAFT
    assert request.days == 7


def test_submit_drafts_success(db_session, vacation_type, min_duration_setting, balance_7):
    request = submit_one(db_session, balance_7, date(2026, 6, 1), date(2026, 6, 7), "отпуск")
    assert request.status == PENDING_APPROVAL
    assert request.days == 7


def test_submit_drafts_rejects_partial_balance(db_session, vacation_type, min_duration_setting, balance_7):
    # Баланс 7 дней, но выбрано (пока) только 7 — если начислено больше, отправка неполного периода запрещена.
    db_session.query(LeaveBalance).filter_by(user_id=balance_7.id, year=2026).update(
        {"accrued_days": 14}
    )
    db_session.flush()
    leave_request_service.create_draft(db_session, balance_7, date(2026, 6, 1), date(2026, 6, 7), None)
    with pytest.raises(ValidationFailedError):
        leave_request_service.submit_drafts(db_session, balance_7, 2026)


def test_cancel_from_pending_approval(db_session, vacation_type, min_duration_setting, balance_7):
    request = submit_one(db_session, balance_7, date(2026, 6, 1), date(2026, 6, 7))
    cancelled = leave_request_service.cancel(db_session, balance_7, request.id)
    assert cancelled.status == CANCELLED
    assert cancelled.cancelled_by == balance_7.id


def test_cancel_from_approved(db_session, vacation_type, min_duration_setting, balance_7):
    request = submit_one(db_session, balance_7, date(2026, 6, 1), date(2026, 6, 7))
    request.status = APPROVED
    db_session.flush()

    cancelled = leave_request_service.cancel(db_session, balance_7, request.id)
    assert cancelled.status == CANCELLED


def test_cancel_rejected_forbidden(db_session, vacation_type, min_duration_setting, balance_7):
    request = submit_one(db_session, balance_7, date(2026, 6, 1), date(2026, 6, 7))
    request.status = REJECTED
    db_session.flush()

    with pytest.raises(ForbiddenError):
        leave_request_service.cancel(db_session, balance_7, request.id)
