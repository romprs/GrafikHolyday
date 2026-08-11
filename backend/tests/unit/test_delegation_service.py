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
