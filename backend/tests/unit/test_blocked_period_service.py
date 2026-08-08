from datetime import date

import pytest

from app.core.exceptions import ForbiddenError
from app.models.blocked_period import GLOBAL, ORG_UNIT, USER
from app.models.org_unit import OrgUnit
from app.models.user import User
from app.services import blocked_period_service


@pytest.fixture()
def hierarchy(db_session):
    hr = User(email="hr@test.local", full_name="HR")
    manager = User(email="manager@test.local", full_name="Manager")
    other_manager = User(email="other-manager@test.local", full_name="Other Manager")
    employee = User(email="employee@test.local", full_name="Employee")
    db_session.add_all([hr, manager, other_manager, employee])
    db_session.flush()

    from app.models.user_role import UserRole

    db_session.add(UserRole(user_id=hr.id, role="hr_admin"))

    division = OrgUnit(name="Управление", head_user_id=None, is_active=True)
    db_session.add(division)
    db_session.flush()

    department = OrgUnit(
        name="Отдел", parent_id=division.id, head_user_id=manager.id, is_active=True
    )
    db_session.add(department)
    db_session.flush()

    employee.org_unit_id = department.id
    db_session.flush()

    return {
        "hr": hr,
        "manager": manager,
        "other_manager": other_manager,
        "employee": employee,
        "division": division,
        "department": department,
    }


def test_global_block_applies_to_everyone(db_session, hierarchy):
    blocked_period_service.create(
        db_session,
        hierarchy["hr"],
        date(2026, 6, 1),
        date(2026, 6, 10),
        "Учебные сборы",
        GLOBAL,
        None,
        None,
    )
    blocks = blocked_period_service.get_effective_blocks(
        db_session, hierarchy["employee"], date(2026, 6, 5), date(2026, 6, 6)
    )
    assert len(blocks) == 1


def test_org_unit_block_on_ancestor_applies_to_employee(db_session, hierarchy):
    # Блок на вышестоящее управление должен действовать на сотрудника отдела ниже.
    blocked_period_service.create(
        db_session,
        hierarchy["hr"],
        date(2026, 7, 1),
        date(2026, 7, 5),
        "Аудит управления",
        ORG_UNIT,
        hierarchy["division"].id,
        None,
    )
    blocks = blocked_period_service.get_effective_blocks(
        db_session, hierarchy["employee"], date(2026, 7, 2), date(2026, 7, 3)
    )
    assert len(blocks) == 1


def test_user_scope_block_applies_only_to_target_user(db_session, hierarchy):
    blocked_period_service.create(
        db_session,
        hierarchy["manager"],
        date(2026, 8, 1),
        date(2026, 8, 3),
        "Индивидуальная учёба",
        USER,
        None,
        hierarchy["employee"].id,
    )
    blocks = blocked_period_service.get_effective_blocks(
        db_session, hierarchy["employee"], date(2026, 8, 1), date(2026, 8, 2)
    )
    assert len(blocks) == 1

    manager_blocks = blocked_period_service.get_effective_blocks(
        db_session, hierarchy["manager"], date(2026, 8, 1), date(2026, 8, 2)
    )
    assert manager_blocks == []


def test_non_overlapping_dates_no_block(db_session, hierarchy):
    blocked_period_service.create(
        db_session,
        hierarchy["hr"],
        date(2026, 6, 1),
        date(2026, 6, 10),
        "Учебные сборы",
        GLOBAL,
        None,
        None,
    )
    blocks = blocked_period_service.get_effective_blocks(
        db_session, hierarchy["employee"], date(2026, 6, 11), date(2026, 6, 15)
    )
    assert blocks == []


def test_manager_cannot_create_global_block(db_session, hierarchy):
    with pytest.raises(ForbiddenError):
        blocked_period_service.create(
            db_session,
            hierarchy["manager"],
            date(2026, 6, 1),
            date(2026, 6, 2),
            "x",
            GLOBAL,
            None,
            None,
        )


def test_manager_cannot_block_foreign_org_unit(db_session, hierarchy):
    with pytest.raises(ForbiddenError):
        blocked_period_service.create(
            db_session,
            hierarchy["other_manager"],
            date(2026, 6, 1),
            date(2026, 6, 2),
            "x",
            ORG_UNIT,
            hierarchy["department"].id,
            None,
        )


def test_manager_can_block_own_department(db_session, hierarchy):
    blocked = blocked_period_service.create(
        db_session,
        hierarchy["manager"],
        date(2026, 6, 1),
        date(2026, 6, 2),
        "x",
        ORG_UNIT,
        hierarchy["department"].id,
        None,
    )
    assert blocked.is_active is True


def test_deactivate_removes_from_effective_blocks(db_session, hierarchy):
    blocked = blocked_period_service.create(
        db_session,
        hierarchy["hr"],
        date(2026, 6, 1),
        date(2026, 6, 2),
        "x",
        GLOBAL,
        None,
        None,
    )
    blocked_period_service.deactivate(db_session, hierarchy["hr"], blocked.id)
    blocks = blocked_period_service.get_effective_blocks(
        db_session, hierarchy["employee"], date(2026, 6, 1), date(2026, 6, 2)
    )
    assert blocks == []
