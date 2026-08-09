from datetime import date

import pytest

from app.models.leave_balance import LeaveBalance
from app.models.leave_request import APPROVED, PENDING_APPROVAL, LeaveRequest
from app.models.leave_type import LeaveType
from app.models.restriction_settings import LEAVE_BALANCE_LIMIT, RestrictionSettings
from app.models.user import User
from app.services import leave_balance_service
from app.services.validation.engine import validate_leave_request


@pytest.fixture()
def setup(db_session):
    db_session.add(RestrictionSettings(key=LEAVE_BALANCE_LIMIT, enabled=True, params={}))
    lt = LeaveType(code="vacation", name_ru="Отпуск")
    db_session.add(lt)
    db_session.flush()
    user = User(email="u@balance.local", full_name="u")
    db_session.add(user)
    db_session.flush()
    db_session.add(LeaveBalance(user_id=user.id, year=2026, accrued_days=10))
    db_session.flush()
    return {"user": user, "leave_type": lt}


def test_request_within_balance_ok(db_session, setup):
    violations = validate_leave_request(db_session, setup["user"], date(2026, 6, 1), date(2026, 6, 7))
    assert not any(v.code == "LEAVE_BALANCE_EXCEEDED" for v in violations)


def test_request_exceeding_balance_rejected(db_session, setup):
    violations = validate_leave_request(db_session, setup["user"], date(2026, 6, 1), date(2026, 6, 15))
    assert any(v.code == "LEAVE_BALANCE_EXCEEDED" for v in violations)


def test_pending_requests_reduce_available_balance(db_session, setup):
    db_session.add(
        LeaveRequest(
            user_id=setup["user"].id,
            leave_type_id=setup["leave_type"].id,
            date_from=date(2026, 3, 1),
            date_to=date(2026, 3, 7),
            status=PENDING_APPROVAL,
        )
    )
    db_session.flush()

    # Остаток 10 - 7 (pending) = 3, запрос на 7 дней должен быть отклонён
    violations = validate_leave_request(db_session, setup["user"], date(2026, 6, 1), date(2026, 6, 7))
    assert any(v.code == "LEAVE_BALANCE_EXCEEDED" for v in violations)


def test_benefits_user_bypasses_balance_limit(db_session, setup):
    setup["user"].has_benefits = True
    db_session.flush()
    violations = validate_leave_request(db_session, setup["user"], date(2026, 6, 1), date(2026, 6, 20))
    assert not any(v.code == "LEAVE_BALANCE_EXCEEDED" for v in violations)


def test_set_balance_creates_and_updates(db_session):
    hr = User(email="hr2@balance.local", full_name="hr")
    employee = User(email="e2@balance.local", full_name="e")
    db_session.add_all([hr, employee])
    db_session.flush()

    balance = leave_balance_service.set_balance(db_session, hr, employee, 2027, 28, 2)
    assert balance.accrued_days == 28
    assert balance.carried_over_days == 2
    assert balance.updated_by == hr.id

    balance2 = leave_balance_service.set_balance(db_session, hr, employee, 2027, 30, 0)
    assert balance2.id == balance.id
    assert balance2.accrued_days == 30


def test_get_remaining_for_new_request_excludes_given_ids(db_session, setup):
    request = LeaveRequest(
        user_id=setup["user"].id,
        leave_type_id=setup["leave_type"].id,
        date_from=date(2026, 3, 1),
        date_to=date(2026, 3, 7),
        status=APPROVED,
    )
    db_session.add(request)
    db_session.flush()

    remaining_including = leave_balance_service.get_remaining_for_new_request(
        db_session, setup["user"], 2026
    )
    remaining_excluding = leave_balance_service.get_remaining_for_new_request(
        db_session, setup["user"], 2026, exclude_request_ids={request.id}
    )
    assert remaining_including == 3
    assert remaining_excluding == 10
