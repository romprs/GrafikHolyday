import pytest

from app.core.exceptions import ForbiddenError, ValidationFailedError
from app.models.org_unit import OrgUnit
from app.models.user import User
from app.services import delegation_service


@pytest.fixture()
def scenario(db_session):
    manager = User(email="manager@d.local", full_name="Manager")
    employee = User(email="employee@d.local", full_name="Employee")
    other_dept_delegate = User(email="delegate@d.local", full_name="Delegate")
    outsider = User(email="outsider@d.local", full_name="Outsider")
    db_session.add_all([manager, employee, other_dept_delegate, outsider])
    db_session.flush()

    unit = OrgUnit(name="Отдел", head_user_id=manager.id, is_active=True)
    db_session.add(unit)
    db_session.flush()
    employee.org_unit_id = unit.id
    db_session.flush()

    return {
        "manager": manager,
        "employee": employee,
        "delegate": other_dept_delegate,
        "outsider": outsider,
    }


def test_manager_grants_delegation_for_own_report(db_session, scenario):
    delegation = delegation_service.grant(
        db_session, scenario["manager"], scenario["delegate"].id, scenario["employee"].id
    )
    assert delegation.is_active
    assert delegation_service.can_act_for(db_session, scenario["delegate"], scenario["employee"].id)


def test_manager_cannot_delegate_outsider(db_session, scenario):
    with pytest.raises(ForbiddenError):
        delegation_service.grant(
            db_session, scenario["manager"], scenario["delegate"].id, scenario["outsider"].id
        )


def test_self_delegation_rejected(db_session, scenario):
    with pytest.raises(ValidationFailedError):
        delegation_service.grant(
            db_session, scenario["manager"], scenario["employee"].id, scenario["employee"].id
        )


def test_revoke_delegation(db_session, scenario):
    delegation = delegation_service.grant(
        db_session, scenario["manager"], scenario["delegate"].id, scenario["employee"].id
    )
    delegation_service.revoke(db_session, scenario["manager"], delegation.id)
    assert not delegation_service.can_act_for(
        db_session, scenario["delegate"], scenario["employee"].id
    )


def test_can_act_for_self_always_true(db_session, scenario):
    assert delegation_service.can_act_for(
        db_session, scenario["employee"], scenario["employee"].id
    )


def test_no_delegation_cannot_act(db_session, scenario):
    assert not delegation_service.can_act_for(
        db_session, scenario["delegate"], scenario["employee"].id
    )


def test_list_targets_for_delegate(db_session, scenario):
    delegation_service.grant(
        db_session, scenario["manager"], scenario["delegate"].id, scenario["employee"].id
    )
    targets = delegation_service.list_targets_for_delegate(db_session, scenario["delegate"])
    assert [t.id for t in targets] == [scenario["employee"].id]


@pytest.fixture()
def unit_scenario(db_session):
    manager = User(email="top-manager@d.local", full_name="TopManager")
    delegate = User(email="unit-delegate@d.local", full_name="UnitDelegate")
    employee1 = User(email="e1@d.local", full_name="E1")
    employee2 = User(email="e2@d.local", full_name="E2")
    outsider = User(email="out@d.local", full_name="Out")
    db_session.add_all([manager, delegate, employee1, employee2, outsider])
    db_session.flush()

    parent_unit = OrgUnit(name="Управление", head_user_id=manager.id, is_active=True)
    db_session.add(parent_unit)
    db_session.flush()
    child_unit = OrgUnit(name="Отдел", is_active=True, parent_id=parent_unit.id)
    db_session.add(child_unit)
    db_session.flush()

    employee1.org_unit_id = parent_unit.id
    employee2.org_unit_id = child_unit.id  # нижестоящее подразделение — каскад
    db_session.flush()

    return {
        "manager": manager,
        "delegate": delegate,
        "employee1": employee1,
        "employee2": employee2,
        "outsider": outsider,
        "parent_unit": parent_unit,
        "child_unit": child_unit,
    }


def test_org_unit_delegation_covers_whole_branch(db_session, unit_scenario):
    delegation_service.grant(
        db_session,
        unit_scenario["manager"],
        unit_scenario["delegate"].id,
        target_org_unit_id=unit_scenario["parent_unit"].id,
    )
    assert delegation_service.can_act_for(
        db_session, unit_scenario["delegate"], unit_scenario["employee1"].id
    )
    # Каскад — сотрудник нижестоящего (child_unit) отдела тоже покрыт.
    assert delegation_service.can_act_for(
        db_session, unit_scenario["delegate"], unit_scenario["employee2"].id
    )
    assert not delegation_service.can_act_for(
        db_session, unit_scenario["delegate"], unit_scenario["outsider"].id
    )


def test_org_unit_delegation_requires_target_or_unit_not_both(db_session, unit_scenario):
    with pytest.raises(ValidationFailedError):
        delegation_service.grant(
            db_session,
            unit_scenario["manager"],
            unit_scenario["delegate"].id,
            target_user_id=unit_scenario["employee1"].id,
            target_org_unit_id=unit_scenario["parent_unit"].id,
        )
    with pytest.raises(ValidationFailedError):
        delegation_service.grant(db_session, unit_scenario["manager"], unit_scenario["delegate"].id)


def test_manager_cannot_delegate_unit_outside_own_scope(db_session, unit_scenario):
    outside_unit = OrgUnit(name="Другое управление", is_active=True)
    db_session.add(outside_unit)
    db_session.flush()
    with pytest.raises(ForbiddenError):
        delegation_service.grant(
            db_session,
            unit_scenario["manager"],
            unit_scenario["delegate"].id,
            target_org_unit_id=outside_unit.id,
        )


def test_list_targets_for_delegate_includes_unit_cascade(db_session, unit_scenario):
    delegation_service.grant(
        db_session,
        unit_scenario["manager"],
        unit_scenario["delegate"].id,
        target_org_unit_id=unit_scenario["parent_unit"].id,
    )
    targets = delegation_service.list_targets_for_delegate(db_session, unit_scenario["delegate"])
    target_ids = {t.id for t in targets}
    assert target_ids == {unit_scenario["employee1"].id, unit_scenario["employee2"].id}
