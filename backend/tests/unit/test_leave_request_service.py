from datetime import date

import pytest

from app.core.exceptions import ForbiddenError, ValidationFailedError
from app.models.leave_request import APPROVED, CANCELLED, PENDING_APPROVAL, REJECTED, LeaveRequest
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


def test_create_and_submit_raises_on_violation(
    db_session, vacation_type, min_duration_setting, employee
):
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_and_submit(
            db_session, employee, date(2026, 6, 1), date(2026, 6, 3), None
        )


def test_create_and_submit_success(db_session, vacation_type, min_duration_setting, employee):
    request = leave_request_service.create_and_submit(
        db_session, employee, date(2026, 6, 1), date(2026, 6, 7), "отпуск"
    )
    assert request.status == PENDING_APPROVAL
    assert request.days == 7


def test_cancel_from_pending_approval(db_session, vacation_type, min_duration_setting, employee):
    request = leave_request_service.create_and_submit(
        db_session, employee, date(2026, 6, 1), date(2026, 6, 7), None
    )
    cancelled = leave_request_service.cancel(db_session, employee, request.id)
    assert cancelled.status == CANCELLED
    assert cancelled.cancelled_by == employee.id


def test_cancel_from_approved(db_session, vacation_type, min_duration_setting, employee):
    request = leave_request_service.create_and_submit(
        db_session, employee, date(2026, 6, 1), date(2026, 6, 7), None
    )
    request.status = APPROVED
    db_session.flush()

    cancelled = leave_request_service.cancel(db_session, employee, request.id)
    assert cancelled.status == CANCELLED


def test_cancel_rejected_forbidden(db_session, vacation_type, min_duration_setting, employee):
    request = leave_request_service.create_and_submit(
        db_session, employee, date(2026, 6, 1), date(2026, 6, 7), None
    )
    request.status = REJECTED
    db_session.flush()

    with pytest.raises(ForbiddenError):
        leave_request_service.cancel(db_session, employee, request.id)
