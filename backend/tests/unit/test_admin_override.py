from datetime import date

import pytest

from app.core.exceptions import ValidationFailedError
from app.models.audit_log import AuditLog
from app.models.leave_request import APPROVED, CANCELLED, LeaveRequest
from app.models.leave_type import LeaveType
from app.models.user import User
from app.models.user_role import UserRole
from app.services import approval_service


@pytest.fixture()
def scenario(db_session):
    hr = User(email="hr@override.local", full_name="hr")
    employee = User(email="e@override.local", full_name="e")
    db_session.add_all([hr, employee])
    db_session.flush()
    db_session.add(UserRole(user_id=hr.id, role="hr_admin"))

    lt = LeaveType(code="vacation", name_ru="Отпуск")
    db_session.add(lt)
    db_session.flush()

    request = LeaveRequest(
        user_id=employee.id,
        leave_type_id=lt.id,
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 7),
        status=APPROVED,
    )
    db_session.add(request)
    db_session.flush()

    return {"hr": hr, "employee": employee, "request": request}


def test_override_requires_reason(db_session, scenario):
    with pytest.raises(ValidationFailedError):
        approval_service.admin_override(
            db_session, scenario["hr"], scenario["request"].id, reason="  "
        )


def test_override_changes_dates_and_writes_audit_log(db_session, scenario):
    result = approval_service.admin_override(
        db_session,
        scenario["hr"],
        scenario["request"].id,
        reason="Перенос по договорённости с сотрудником",
        date_from=date(2026, 6, 3),
        date_to=date(2026, 6, 9),
    )
    assert result.date_from == date(2026, 6, 3)
    assert result.date_to == date(2026, 6, 9)

    logs = db_session.query(AuditLog).filter_by(entity_id=scenario["request"].id).all()
    assert len(logs) == 1
    assert logs[0].reason == "Перенос по договорённости с сотрудником"
    assert logs[0].before_state["date_from"] == "2026-06-01"
    assert logs[0].after_state["date_from"] == "2026-06-03"
    assert logs[0].performed_by == scenario["hr"].id


def test_override_works_regardless_of_status(db_session, scenario):
    scenario["request"].status = CANCELLED
    db_session.flush()

    result = approval_service.admin_override(
        db_session,
        scenario["hr"],
        scenario["request"].id,
        reason="Восстановление по ошибке отмены",
        status=APPROVED,
    )
    assert result.status == APPROVED


def test_override_rejects_invalid_date_range(db_session, scenario):
    with pytest.raises(ValidationFailedError):
        approval_service.admin_override(
            db_session,
            scenario["hr"],
            scenario["request"].id,
            reason="x",
            date_from=date(2026, 6, 10),
            date_to=date(2026, 6, 5),
        )
