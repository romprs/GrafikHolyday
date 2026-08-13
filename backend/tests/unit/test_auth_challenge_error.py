from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import AuthChallengeError, ForbiddenError, register_exception_handlers

_app = FastAPI()
register_exception_handlers(_app)


@_app.get("/needs-negotiate")
def _needs_negotiate():
    raise AuthChallengeError("Требуется Kerberos-аутентификация", www_authenticate="Negotiate")


@_app.get("/plain-forbidden")
def _plain_forbidden():
    raise ForbiddenError("Нет доступа")


_client = TestClient(_app)


def test_auth_challenge_error_sets_www_authenticate_header_and_401():
    response = _client.get("/needs-negotiate")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Negotiate"
    assert response.json()["code"] == "AUTH_CHALLENGE"


def test_forbidden_error_has_no_www_authenticate_header():
    response = _client.get("/plain-forbidden")
    assert response.status_code == 403
    assert "www-authenticate" not in {k.lower() for k in response.headers}
