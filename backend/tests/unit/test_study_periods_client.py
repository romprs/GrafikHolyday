from datetime import date

import httpx
import pytest

from app.integrations.study_periods import StudyPeriodsClient


class _FakeResponse:
    def __init__(self, status_code: int, json_data=None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text if text else ("" if json_data is None else str(json_data))
        self.is_error = status_code >= 400

    def json(self):
        if self._json_data is None:
            raise ValueError("no json")
        return self._json_data


@pytest.fixture()
def client():
    return StudyPeriodsClient(base_url="https://source.example/study_plan", login="u", password="p")


def test_test_fetch_success_reports_request_and_parsed_count(client, monkeypatch):
    """Реальный формат ответа источника (плоский список, без обёртки по
    табельному номеру; ключ "ПрограмаОбучения" — с одной "м"; дата ISO 8601)."""

    def fake_get(url, params=None, auth=None, verify=None, timeout=None):
        return _FakeResponse(
            200,
            json_data=[
                {"ПрограмаОбучения": "Курс", "Дата": "2027-10-24T00:00:00", "КолВоЧасов": 16}
            ],
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    result = client.test_fetch("3168", date(2027, 1, 1), date(2027, 12, 31))

    assert result["error"] is None
    assert result["http_status"] == 200
    assert result["parsed_entries_count"] == 1
    assert "Employee=3168" in result["request_url"]
    assert "source.example" in result["request_url"]


def test_test_fetch_reports_http_error(client, monkeypatch):
    def fake_get(url, params=None, auth=None, verify=None, timeout=None):
        return _FakeResponse(404, text="Not Found")

    monkeypatch.setattr(httpx, "get", fake_get)
    result = client.test_fetch("9999", date(2027, 1, 1), date(2027, 12, 31))

    assert result["http_status"] == 404
    assert "404" in result["error"]
    assert result["response_body_preview"] == "Not Found"
    assert result["parsed_entries_count"] is None


def test_test_fetch_reports_connection_error(client, monkeypatch):
    def fake_get(url, params=None, auth=None, verify=None, timeout=None):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", fake_get)
    result = client.test_fetch("3168", date(2027, 1, 1), date(2027, 12, 31))

    assert result["http_status"] is None
    assert "Не удалось соединиться" in result["error"]


def test_test_fetch_reports_invalid_json(client, monkeypatch):
    def fake_get(url, params=None, auth=None, verify=None, timeout=None):
        return _FakeResponse(200, json_data=None, text="<html>not json</html>")

    monkeypatch.setattr(httpx, "get", fake_get)
    result = client.test_fetch("3168", date(2027, 1, 1), date(2027, 12, 31))

    assert result["http_status"] == 200
    assert "JSON" in result["error"]


def test_test_fetch_reports_unexpected_response_shape(client, monkeypatch):
    """Ответ пришёл валидным JSON, HTTP 200 — но не в ожидаемом формате
    (например, источник поменял контракт). Должно быть видно как отдельная
    причина, а не тихо посчитаться как "0 записей"."""

    def fake_get(url, params=None, auth=None, verify=None, timeout=None):
        return _FakeResponse(200, json_data=[{"unexpected": "shape"}])

    monkeypatch.setattr(httpx, "get", fake_get)
    result = client.test_fetch("3168", date(2027, 1, 1), date(2027, 12, 31))

    assert result["error"] is not None
    assert result["parsed_entries_count"] is None
