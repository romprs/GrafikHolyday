from datetime import date

import pytest

from app.models.leave_request import APPROVED, CANCELLED, PENDING_APPROVAL, LeaveRequest
from app.models.leave_type import LeaveType
from app.models.restriction_settings import OWN_OVERLAP_CHECK, RestrictionSettings
from app.models.user import User
from app.services.validation.engine import validate_leave_request


@pytest.fixture()
def setup(db_session):
    db_session.add(RestrictionSettings(key=OWN_OVERLAP_CHECK, enabled=True, params={}))
    lt = LeaveType(code="vacation", name_ru="Отпуск")
    db_session.add(lt)
    db_session.flush()
    user = User(email="u@overlap.local", full_name="u")
    db_session.add(user)
    db_session.flush()
    return {"user": user, "leave_type": lt}


def _add_request(db_session, setup, date_from, date_to, status):
    db_session.add(
        LeaveRequest(
            user_id=setup["user"].id,
            leave_type_id=setup["leave_type"].id,
            date_from=date_from,
            date_to=date_to,
            status=status,
        )
    )
    db_session.flush()


def test_overlaps_pending_request(db_session, setup):
    _add_request(db_session, setup, date(2026, 6, 1), date(2026, 6, 10), PENDING_APPROVAL)
    violations = validate_leave_request(db_session, setup["user"], date(2026, 6, 5), date(2026, 6, 15))
    assert any(v.code == "OWN_REQUEST_OVERLAP" for v in violations)


def test_overlaps_approved_request(db_session, setup):
    _add_request(db_session, setup, date(2026, 6, 1), date(2026, 6, 10), APPROVED)
    violations = validate_leave_request(db_session, setup["user"], date(2026, 6, 10), date(2026, 6, 17))
    assert any(v.code == "OWN_REQUEST_OVERLAP" for v in violations)


def test_does_not_overlap_cancelled_request(db_session, setup):
    _add_request(db_session, setup, date(2026, 6, 1), date(2026, 6, 10), CANCELLED)
    violations = validate_leave_request(db_session, setup["user"], date(2026, 6, 5), date(2026, 6, 15))
    assert not any(v.code == "OWN_REQUEST_OVERLAP" for v in violations)


def test_non_overlapping_ok(db_session, setup):
    _add_request(db_session, setup, date(2026, 6, 1), date(2026, 6, 10), APPROVED)
    violations = validate_leave_request(db_session, setup["user"], date(2026, 6, 11), date(2026, 6, 17))
    assert not any(v.code == "OWN_REQUEST_OVERLAP" for v in violations)


def test_benefits_user_still_checked(db_session, setup):
    setup["user"].has_benefits = True
    db_session.flush()
    _add_request(db_session, setup, date(2026, 6, 1), date(2026, 6, 10), APPROVED)
    violations = validate_leave_request(db_session, setup["user"], date(2026, 6, 5), date(2026, 6, 15))
    assert any(v.code == "OWN_REQUEST_OVERLAP" for v in violations)
