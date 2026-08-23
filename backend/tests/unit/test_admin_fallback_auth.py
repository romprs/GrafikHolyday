import pytest

from app.config import settings
from app.core.exceptions import ForbiddenError
from app.dependencies import get_current_user
from app.models.user import User
from app.models.user_role import UserRole


@pytest.fixture()
def hr_admin_user(db_session):
    user = User(email="hr@fallback.local", full_name="HR", is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role="hr_admin"))
    db_session.commit()
    return user


@pytest.fixture()
def employee_user(db_session):
    user = User(email="employee@fallback.local", full_name="Employee", is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture(autouse=True)
def _configured_password(monkeypatch):
    monkeypatch.setattr(settings, "admin_fallback_password", "correct-horse-battery-staple")
    yield


def test_fallback_login_succeeds_for_hr_admin(db_session, hr_admin_user):
    result = get_current_user(
        request=None,
        db=db_session,
        x_admin_fallback_email="hr@fallback.local",
        x_admin_fallback_password="correct-horse-battery-staple",
    )
    assert result.id == hr_admin_user.id


def test_fallback_login_is_case_insensitive_on_email(db_session, hr_admin_user):
    result = get_current_user(
        request=None,
        db=db_session,
        x_admin_fallback_email="HR@FALLBACK.LOCAL",
        x_admin_fallback_password="correct-horse-battery-staple",
    )
    assert result.id == hr_admin_user.id


def test_fallback_login_rejects_wrong_password(db_session, hr_admin_user):
    with pytest.raises(ForbiddenError):
        get_current_user(
            request=None,
            db=db_session,
            x_admin_fallback_email="hr@fallback.local",
            x_admin_fallback_password="wrong-password",
        )


def test_fallback_login_rejects_non_hr_admin(db_session, employee_user):
    with pytest.raises(ForbiddenError):
        get_current_user(
            request=None,
            db=db_session,
            x_admin_fallback_email="employee@fallback.local",
            x_admin_fallback_password="correct-horse-battery-staple",
        )


def test_fallback_login_rejects_unknown_email(db_session, hr_admin_user):
    with pytest.raises(ForbiddenError):
        get_current_user(
            request=None,
            db=db_session,
            x_admin_fallback_email="nobody@fallback.local",
            x_admin_fallback_password="correct-horse-battery-staple",
        )


def test_fallback_disabled_when_password_not_configured(db_session, hr_admin_user, monkeypatch):
    monkeypatch.setattr(settings, "admin_fallback_password", None)
    with pytest.raises(ForbiddenError):
        get_current_user(
            request=None,
            db=db_session,
            x_admin_fallback_email="hr@fallback.local",
            x_admin_fallback_password="correct-horse-battery-staple",
        )


def test_fallback_does_not_leak_into_normal_dev_login(db_session, hr_admin_user):
    """Без обоих заголовков сразу должен работать обычный путь (dev/kerberos),
    а не тихо проваливаться в аварийный вход."""
    with pytest.raises(ForbiddenError):
        get_current_user(request=None, db=db_session)
