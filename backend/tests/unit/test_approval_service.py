from datetime import date

import pytest

from app.core.exceptions import ConflictError, ForbiddenError
from app.models.leave_request import APPROVED, PENDING_APPROVAL, REJECTED, LeaveRequest
from app.models.leave_type import LeaveType
from app.models.org_unit import OrgUnit
from app.models.user import User
from app.services import approval_service


@pytest.fixture()
def scenario(db_session):
    lt = LeaveType(code="vacation", name_ru="Отпуск")
    db_session.add(lt)
    db_session.flush()

    manager = User(email="manager@test.local", full_name="Manager")
    other_manager = User(email="other@test.local", full_name="Other")
    employee = User(email="employee@test.local", full_name="Employee")
    db_session.add_all([manager, other_manager, employee])
    db_session.flush()

    unit = OrgUnit(name="Отдел", head_user_id=manager.id, is_active=True)
    db_session.add(unit)
    db_session.flush()
    employee.org_unit_id = unit.id
    db_session.flush()

    request = LeaveRequest(
        user_id=employee.id,
        leave_type_id=lt.id,
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 7),
        status=PENDING_APPROVAL,
    )
    db_session.add(request)
    db_session.flush()

    return {
        "manager": manager,
        "other_manager": other_manager,
        "employee": employee,
        "request": request,
    }


def test_approve_by_direct_manager(db_session, scenario):
    result = approval_service.approve(db_session, scenario["manager"], scenario["request"].id, "ок")
    assert len(result) == 1
    assert result[0].status == APPROVED
    assert result[0].reviewer_id == scenario["manager"].id


def test_approve_by_non_manager_forbidden(db_session, scenario):
    with pytest.raises(ForbiddenError):
        approval_service.approve(db_session, scenario["other_manager"], scenario["request"].id, None)


def test_approve_already_reviewed_conflict(db_session, scenario):
    approval_service.approve(db_session, scenario["manager"], scenario["request"].id, None)
    with pytest.raises(ConflictError):
        approval_service.approve(db_session, scenario["manager"], scenario["request"].id, None)


def test_reject_by_direct_manager(db_session, scenario):
    result = approval_service.reject(db_session, scenario["manager"], scenario["request"].id, "нет")
    assert len(result) == 1
    assert result[0].status == REJECTED


def test_list_pending_for_manager(db_session, scenario):
    pending = approval_service.list_pending_for_manager(db_session, scenario["manager"])
    assert len(pending) == 1
    assert pending[0].id == scenario["request"].id

    pending_other = approval_service.list_pending_for_manager(db_session, scenario["other_manager"])
    assert pending_other == []


def test_manager_cancel_approved(db_session, scenario):
    approval_service.approve(db_session, scenario["manager"], scenario["request"].id, None)
    cancelled = approval_service.manager_cancel_approved(
        db_session, scenario["manager"], scenario["request"].id, "передумали"
    )
    assert len(cancelled) == 1
    assert cancelled[0].status == "cancelled"
    assert cancelled[0].cancelled_by == scenario["manager"].id


def test_manager_cancel_approved_by_non_manager_forbidden(db_session, scenario):
    approval_service.approve(db_session, scenario["manager"], scenario["request"].id, None)
    with pytest.raises(ForbiddenError):
        approval_service.manager_cancel_approved(
            db_session, scenario["other_manager"], scenario["request"].id, None
        )


def test_manager_cancel_pending_conflict(db_session, scenario):
    with pytest.raises(ConflictError):
        approval_service.manager_cancel_approved(
            db_session, scenario["manager"], scenario["request"].id, None
        )


def test_approve_covers_whole_submission(db_session, scenario):
    import uuid

    submission_id = uuid.uuid4()
    scenario["request"].submission_id = submission_id
    second = LeaveRequest(
        user_id=scenario["employee"].id,
        leave_type_id=scenario["request"].leave_type_id,
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 3),
        status=PENDING_APPROVAL,
        submission_id=submission_id,
    )
    db_session.add(second)
    db_session.flush()

    result = approval_service.approve(db_session, scenario["manager"], scenario["request"].id, "ок")

    assert {r.id for r in result} == {scenario["request"].id, second.id}
    assert all(r.status == APPROVED for r in result)


def test_list_approved_for_manager(db_session, scenario):
    approval_service.approve(db_session, scenario["manager"], scenario["request"].id, None)
    approved = approval_service.list_approved_for_manager(db_session, scenario["manager"])
    assert len(approved) == 1
    assert approved[0].id == scenario["request"].id
