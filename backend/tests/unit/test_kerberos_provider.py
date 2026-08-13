import pytest

from app.auth import kerberos_provider
from app.core.exceptions import ForbiddenError
from app.models.user import User


def _make_user(email: str, is_active: bool = True) -> User:
    return User(email=email, full_name=email, is_active=is_active)


@pytest.mark.parametrize(
    "principal,expected",
    [
        ("ivanov@CORP.AMURGPZ.RU", "ivanov"),
        ("ivanov", "ivanov"),
        ("ivanov/admin@CORP.AMURGPZ.RU", "ivanov"),
    ],
)
def test_principal_to_login(principal, expected):
    assert kerberos_provider.principal_to_login(principal) == expected


def test_login_from_trusted_header_strips_realm():
    assert kerberos_provider.login_from_trusted_header("ivanov@CORP.AMURGPZ.RU") == "ivanov"


def test_resolve_login_matches_local_part_of_email_case_insensitively(db_session):
    user = _make_user("Ivanov@corp.amurgpz.ru")
    db_session.add(user)
    db_session.flush()

    resolved = kerberos_provider.resolve_login(db_session, "IVANOV")
    assert resolved.id == user.id


def test_resolve_login_ignores_inactive_user(db_session):
    db_session.add(_make_user("ivanov@corp.amurgpz.ru", is_active=False))
    db_session.flush()

    with pytest.raises(ForbiddenError):
        kerberos_provider.resolve_login(db_session, "ivanov")


def test_resolve_login_no_match_raises(db_session):
    with pytest.raises(ForbiddenError):
        kerberos_provider.resolve_login(db_session, "nobody")


def test_resolve_login_does_not_match_different_local_part_with_like_wildcards(db_session):
    # login "iv" не должен случайно поймать "ivanov@..." через '%'-подстановку —
    # у нас не LIKE 'iv%@%', а точное совпадение локальной части.
    db_session.add(_make_user("ivanov@corp.amurgpz.ru"))
    db_session.flush()

    with pytest.raises(ForbiddenError):
        kerberos_provider.resolve_login(db_session, "iv")


def test_resolve_login_escapes_like_special_characters(db_session):
    # Логин с "%"/"_" не должен вести себя как LIKE-шаблон — тут это просто
    # защита от неожиданных совпадений, а не реалистичный логин.
    db_session.add(_make_user("a_b@corp.amurgpz.ru"))
    db_session.add(_make_user("aXb@corp.amurgpz.ru"))
    db_session.flush()

    resolved = kerberos_provider.resolve_login(db_session, "a_b")
    assert resolved.email == "a_b@corp.amurgpz.ru"


def test_resolve_login_empty_raises(db_session):
    with pytest.raises(ForbiddenError):
        kerberos_provider.resolve_login(db_session, "   ")


def test_gssapi_provider_requires_hostname(monkeypatch):
    import sys
    import types

    fake_gssapi = types.ModuleType("gssapi")
    fake_gssapi.exceptions = types.SimpleNamespace(GSSError=Exception)
    monkeypatch.setitem(sys.modules, "gssapi", fake_gssapi)

    from app.config import settings

    monkeypatch.setattr(settings, "kerberos_server_hostname", None)
    monkeypatch.setattr(settings, "kerberos_keytab_path", "/some/path.keytab")

    with pytest.raises(RuntimeError, match="KERBEROS_SERVER_HOSTNAME"):
        kerberos_provider.KerberosGSSAPIAuthProvider()


def test_gssapi_provider_requires_gssapi_package(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "gssapi":
            raise ImportError("no module named gssapi")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    with pytest.raises(RuntimeError, match="python-gssapi"):
        kerberos_provider.KerberosGSSAPIAuthProvider()


def test_gssapi_authenticate_without_header_challenges():
    from app.core.exceptions import AuthChallengeError

    provider = object.__new__(kerberos_provider.KerberosGSSAPIAuthProvider)
    with pytest.raises(AuthChallengeError):
        kerberos_provider.KerberosGSSAPIAuthProvider.authenticate(provider, None)


def test_gssapi_authenticate_rejects_non_negotiate_scheme():
    from app.core.exceptions import AuthChallengeError

    provider = object.__new__(kerberos_provider.KerberosGSSAPIAuthProvider)
    with pytest.raises(AuthChallengeError):
        kerberos_provider.KerberosGSSAPIAuthProvider.authenticate(provider, "Basic abc123")
