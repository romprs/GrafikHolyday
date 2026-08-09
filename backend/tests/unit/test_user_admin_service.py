import pytest

from app.core.exceptions import ForbiddenError
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
