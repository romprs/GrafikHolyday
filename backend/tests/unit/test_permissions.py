from app.models.org_unit import OrgUnit
from app.models.user import User
from app.models.user_role import UserRole
from app.services import permissions


def _make_user(email: str) -> User:
    return User(email=email, full_name=email)


def test_resolve_role_employee_by_default(db_session):
    user = _make_user("employee@test.local")
    db_session.add(user)
    db_session.flush()

    assert permissions.resolve_role(db_session, user) == permissions.EMPLOYEE


def test_resolve_role_manager_when_heads_active_org_unit(db_session):
    user = _make_user("manager@test.local")
    db_session.add(user)
    db_session.flush()
    db_session.add(OrgUnit(name="Отдел", head_user_id=user.id, is_active=True))
    db_session.flush()

    assert permissions.resolve_role(db_session, user) == permissions.MANAGER


def test_resolve_role_ignores_inactive_org_unit(db_session):
    user = _make_user("ex-manager@test.local")
    db_session.add(user)
    db_session.flush()
    db_session.add(OrgUnit(name="Расформированный отдел", head_user_id=user.id, is_active=False))
    db_session.flush()

    assert permissions.resolve_role(db_session, user) == permissions.EMPLOYEE


def test_resolve_role_hr_admin_takes_priority_over_manager(db_session):
    user = _make_user("hr@test.local")
    db_session.add(user)
    db_session.flush()
    db_session.add(OrgUnit(name="Отдел", head_user_id=user.id, is_active=True))
    db_session.add(UserRole(user_id=user.id, role="hr_admin"))
    db_session.flush()

    assert permissions.resolve_role(db_session, user) == permissions.HR_ADMIN
