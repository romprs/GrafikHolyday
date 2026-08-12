import pytest

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationFailedError
from app.models.org_unit import OrgUnit
from app.models.user import User
from app.models.user_role import UserRole
from app.services import permissions, user_admin_service


@pytest.fixture()
def users(db_session):
    hr = User(email="hr@admin.local", full_name="hr")
    employee = User(email="e@admin.local", full_name="e")
    db_session.add_all([hr, employee])
    db_session.flush()
    db_session.add(UserRole(user_id=hr.id, role="hr_admin"))
    db_session.flush()
    return {"hr": hr, "employee": employee}


def test_list_users_with_roles(db_session, users):
    result = dict(
        (u.email, role) for u, role in user_admin_service.list_users_with_roles(db_session)
    )
    assert result["hr@admin.local"] == permissions.HR_ADMIN
    assert result["e@admin.local"] == permissions.EMPLOYEE


def test_grant_role_makes_user_hr_admin(db_session, users):
    user_admin_service.grant_role(db_session, users["hr"], users["employee"].id, "hr_admin")
    role = permissions.resolve_role(db_session, users["employee"])
    assert role == permissions.HR_ADMIN


def test_grant_role_idempotent(db_session, users):
    user_admin_service.grant_role(db_session, users["hr"], users["employee"].id, "hr_admin")
    user_admin_service.grant_role(db_session, users["hr"], users["employee"].id, "hr_admin")
    count = (
        db_session.query(UserRole)
        .filter_by(user_id=users["employee"].id, role="hr_admin")
        .count()
    )
    assert count == 1


def test_revoke_role(db_session, users):
    user_admin_service.grant_role(db_session, users["hr"], users["employee"].id, "hr_admin")
    user_admin_service.revoke_role(db_session, users["hr"], users["employee"].id, "hr_admin")
    role = permissions.resolve_role(db_session, users["employee"])
    assert role == permissions.EMPLOYEE


def test_cannot_revoke_own_role(db_session, users):
    with pytest.raises(ForbiddenError):
        user_admin_service.revoke_role(db_session, users["hr"], users["hr"].id, "hr_admin")


def test_set_employee_code(db_session, users):
    updated = user_admin_service.set_employee_code(db_session, users["employee"].id, "2800")
    assert updated.employee_code == "2800"


def test_set_employee_code_rejects_duplicate(db_session, users):
    user_admin_service.set_employee_code(db_session, users["hr"].id, "2800")
    with pytest.raises(ValidationFailedError):
        user_admin_service.set_employee_code(db_session, users["employee"].id, "2800")


def test_set_employee_code_clears_with_blank(db_session, users):
    user_admin_service.set_employee_code(db_session, users["employee"].id, "2800")
    cleared = user_admin_service.set_employee_code(db_session, users["employee"].id, "  ")
    assert cleared.employee_code is None


def test_create_user(db_session, users):
    unit = OrgUnit(name="Отдел")
    db_session.add(unit)
    db_session.flush()

    user = user_admin_service.create_user(
        db_session, "new@test.local", "Новый Сотрудник", unit.id, False, "3300"
    )
    assert user.email == "new@test.local"
    assert user.org_unit_id == unit.id
    assert user.employee_code == "3300"


def test_create_user_rejects_duplicate_email(db_session, users):
    with pytest.raises(ValidationFailedError):
        user_admin_service.create_user(db_session, "hr@admin.local", "Клон", None, False, None)


def test_create_user_rejects_unknown_org_unit(db_session, users):
    import uuid

    with pytest.raises(NotFoundError):
        user_admin_service.create_user(db_session, "new@test.local", "Новый", uuid.uuid4(), False, None)


def test_update_user(db_session, users):
    updated = user_admin_service.update_user(
        db_session, users["employee"].id, "renamed@test.local", "Переименован", None, True, True
    )
    assert updated.email == "renamed@test.local"
    assert updated.has_benefits is True


def test_deactivate_user_clears_head_of_unit(db_session, users):
    unit = OrgUnit(name="Отдел", head_user_id=users["employee"].id)
    db_session.add(unit)
    db_session.flush()

    user_admin_service.deactivate_user(db_session, users["employee"].id)
    db_session.refresh(unit)
    assert unit.head_user_id is None
