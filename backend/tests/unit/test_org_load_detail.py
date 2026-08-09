from datetime import date

import pytest

from app.models.leave_request import APPROVED, DRAFT, PENDING_APPROVAL, LeaveRequest
from app.models.leave_type import LeaveType
from app.models.org_unit import OrgUnit
from app.models.user import User
from app.services import org_load_service


@pytest.fixture()
def scenario(db_session):
    lt = LeaveType(code="vacation", name_ru="Отпуск")
    db_session.add(lt)
    db_session.flush()

    dept = OrgUnit(name="Отдел", is_active=True)
    db_session.add(dept)
    db_session.flush()

    manager = User(email="m@detail.local", full_name="Иван Начальников", org_unit_id=dept.id)
    employee = User(email="e@detail.local", full_name="Пётр Работников", org_unit_id=dept.id)
    db_session.add_all([manager, employee])
    db_session.flush()
    dept.head_user_id = manager.id
    db_session.flush()

    db_session.add(
        LeaveRequest(
            user_id=employee.id,
            leave_type_id=lt.id,
            date_from=date(2026, 6, 1),
            date_to=date(2026, 6, 5),
            status=APPROVED,
        )
    )
    db_session.flush()

    return {"dept": dept, "manager": manager, "employee": employee, "leave_type": lt}


def test_employees_include_resolved_role(db_session, scenario):
    result = org_load_service.get_org_leave_detail(
        db_session, scenario["dept"].id, date(2026, 6, 1), date(2026, 6, 30)
    )
    roles = {e["full_name"]: e["role"] for e in result["employees"]}
    assert roles["Иван Начальников"] == "manager"
    assert roles["Пётр Работников"] == "employee"


def test_leaves_within_range(db_session, scenario):
    result = org_load_service.get_org_leave_detail(
        db_session, scenario["dept"].id, date(2026, 6, 1), date(2026, 6, 30)
    )
    assert len(result["leaves"]) == 1
    assert result["leaves"][0]["user_id"] == scenario["employee"].id
    assert result["leaves"][0]["status"] == APPROVED


def test_leaves_outside_range_excluded(db_session, scenario):
    result = org_load_service.get_org_leave_detail(
        db_session, scenario["dept"].id, date(2026, 7, 1), date(2026, 7, 30)
    )
    assert result["leaves"] == []


def test_leaves_include_draft_and_pending(db_session, scenario):
    db_session.add_all(
        [
            LeaveRequest(
                user_id=scenario["employee"].id,
                leave_type_id=scenario["leave_type"].id,
                date_from=date(2026, 6, 10),
                date_to=date(2026, 6, 12),
                status=DRAFT,
            ),
            LeaveRequest(
                user_id=scenario["manager"].id,
                leave_type_id=scenario["leave_type"].id,
                date_from=date(2026, 6, 15),
                date_to=date(2026, 6, 17),
                status=PENDING_APPROVAL,
            ),
        ]
    )
    db_session.flush()

    result = org_load_service.get_org_leave_detail(
        db_session, scenario["dept"].id, date(2026, 6, 1), date(2026, 6, 30)
    )
    statuses = {r["status"] for r in result["leaves"]}
    assert statuses == {APPROVED, DRAFT, PENDING_APPROVAL}
