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


def test_upper_manager_approves_employee_of_child_unit(db_session):
    lt = LeaveType(code="vacation", name_ru="Отпуск")
    db_session.add(lt)
    db_session.flush()

    top_manager = User(email="top@test.local", full_name="Top")
    sub_manager = User(email="sub@test.local", full_name="Sub")
    employee = User(email="child-emp@test.local", full_name="ChildEmp")
    db_session.add_all([top_manager, sub_manager, employee])
    db_session.flush()

    parent_unit = OrgUnit(name="Управление", head_user_id=top_manager.id, is_active=True)
    db_session.add(parent_unit)
    db_session.flush()
    child_unit = OrgUnit(
        name="Отдел", head_user_id=sub_manager.id, is_active=True, parent_id=parent_unit.id
    )
    db_session.add(child_unit)
    db_session.flush()
    employee.org_unit_id = child_unit.id
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

    # Вышестоящий руководитель (parent_unit) видит и может согласовать
    # заявку сотрудника из нижестоящего отдела (child_unit).
    pending = approval_service.list_pending_for_manager(db_session, top_manager)
    assert len(pending) == 1

    result = approval_service.approve(db_session, top_manager, request.id, None)
    assert result[0].status == APPROVED


def test_list_approved_for_manager(db_session, scenario):
    approval_service.approve(db_session, scenario["manager"], scenario["request"].id, None)
    approved = approval_service.list_approved_for_manager(db_session, scenario["manager"])
    assert len(approved) == 1


@pytest.fixture()
def hierarchy(db_session):
    """top_manager возглавляет корневое подразделение (без родителя —
    аналог замгендиректора), sub_manager — дочернее (обычный руководитель
    структурного подразделения, у которого есть вышестоящий)."""
    lt = LeaveType(code="vacation", name_ru="Отпуск")
    db_session.add(lt)
    db_session.flush()

    top_manager = User(email="top@test.local", full_name="Top")
    sub_manager = User(email="sub@test.local", full_name="Sub")
    db_session.add_all([top_manager, sub_manager])
    db_session.flush()

    parent_unit = OrgUnit(name="Управление", head_user_id=top_manager.id, is_active=True)
    db_session.add(parent_unit)
    db_session.flush()
    child_unit = OrgUnit(
        name="Отдел", head_user_id=sub_manager.id, is_active=True, parent_id=parent_unit.id
    )
    db_session.add(child_unit)
    db_session.flush()
    top_manager.org_unit_id = parent_unit.id
    sub_manager.org_unit_id = child_unit.id
    db_session.flush()

    return {
        "top_manager": top_manager,
        "sub_manager": sub_manager,
        "parent_unit": parent_unit,
        "child_unit": child_unit,
        "leave_type": lt,
    }


def _submit_own_request(db_session, hierarchy, user) -> LeaveRequest:
    request = LeaveRequest(
        user_id=user.id,
        leave_type_id=hierarchy["leave_type"].id,
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 7),
        status=PENDING_APPROVAL,
    )
    db_session.add(request)
    db_session.flush()
    return request


def test_department_head_cannot_self_approve_own_request(db_session, hierarchy):
    """Баг из продакшена: руководитель структурного подразделения мог
    согласовать сам себе заявку (каскад видимости включает его собственный
    отдел). Должно уходить вышестоящему руководителю."""
    request = _submit_own_request(db_session, hierarchy, hierarchy["sub_manager"])
    with pytest.raises(ForbiddenError):
        approval_service.approve(db_session, hierarchy["sub_manager"], request.id, None)


def test_department_head_own_request_approved_by_upper_manager(db_session, hierarchy):
    """Заявка руководителя подразделения согласовывается вышестоящим по
    иерархии (руководителем родительского подразделения)."""
    request = _submit_own_request(db_session, hierarchy, hierarchy["sub_manager"])
    result = approval_service.approve(db_session, hierarchy["top_manager"], request.id, None)
    assert result[0].status == APPROVED


def test_department_head_own_request_hidden_from_own_queue(db_session, hierarchy):
    """Иначе руководитель увидел бы в своей очереди заявку, которую сам
    согласовать не может (кнопка «Согласовать» была бы нерабочей)."""
    _submit_own_request(db_session, hierarchy, hierarchy["sub_manager"])
    pending = approval_service.list_pending_for_manager(db_session, hierarchy["sub_manager"])
    assert pending == []

    # Но у вышестоящего руководителя эта заявка в очереди есть.
    pending_for_top = approval_service.list_pending_for_manager(db_session, hierarchy["top_manager"])
    assert len(pending_for_top) == 1


def test_top_level_head_exempt_from_self_approval_restriction(db_session, hierarchy):
    """Исключение по требованию: уровень заместителя генерального
    директора (подразделение без родителя) — выше согласовывать некому,
    старое поведение (самосогласование) сохраняется."""
    request = _submit_own_request(db_session, hierarchy, hierarchy["top_manager"])
    result = approval_service.approve(db_session, hierarchy["top_manager"], request.id, None)
    assert result[0].status == APPROVED


def test_top_level_head_own_request_visible_in_own_queue(db_session, hierarchy):
    _submit_own_request(db_session, hierarchy, hierarchy["top_manager"])
    pending = approval_service.list_pending_for_manager(db_session, hierarchy["top_manager"])
    assert len(pending) == 1


def test_approve_by_deputy_with_is_approver_flag(db_session, scenario):
    # Заместитель — не head_user_id юнита, но состоит в нём и явно получил
    # право согласования (см. User.is_approver, org_unit_service.approval_unit_ids).
    deputy = User(email="deputy@test.local", full_name="Deputy", is_approver=True)
    db_session.add(deputy)
    db_session.flush()
    deputy.org_unit_id = scenario["employee"].org_unit_id
    db_session.flush()

    result = approval_service.approve(db_session, deputy, scenario["request"].id, "за руководителя")
    assert result[0].status == APPROVED
    assert result[0].reviewer_id == deputy.id


def test_deputy_without_flag_still_forbidden(db_session, scenario):
    plain_colleague = User(
        email="colleague@test.local", full_name="Colleague", org_unit_id=scenario["employee"].org_unit_id
    )
    db_session.add(plain_colleague)
    db_session.flush()

    with pytest.raises(ForbiddenError):
        approval_service.approve(db_session, plain_colleague, scenario["request"].id, None)
