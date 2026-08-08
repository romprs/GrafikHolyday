import pytest

from app.models.external_id_mapping import ExternalIdMapping
from app.models.org_unit import OrgUnit
from app.models.user import User
from app.services import sync_service
from app.sync.fake_client import FakeDirectoryClient


@pytest.fixture()
def client():
    return FakeDirectoryClient()


def test_first_run_creates_org_units_and_users(db_session, client):
    run = sync_service.run_sync(db_session, client, "manual", None)

    assert run.status == "success"
    assert run.summary["org_units"]["created"] == 5
    assert run.summary["users"]["created"] == 8

    units = db_session.query(OrgUnit).all()
    users = db_session.query(User).all()
    assert len(units) == 5
    assert len(users) == 8


def test_hierarchy_and_head_resolved_correctly(db_session, client):
    sync_service.run_sync(db_session, client, "manual", None)

    backend_dept = db_session.query(OrgUnit).filter_by(name="Отдел бэкенда").one()
    division = db_session.query(OrgUnit).filter_by(name="Управление разработки").one()
    assert backend_dept.parent_id == division.id

    head = db_session.query(User).filter_by(email="backend.head@example.com").one()
    assert backend_dept.head_user_id == head.id


def test_second_run_with_same_data_is_idempotent(db_session, client):
    sync_service.run_sync(db_session, client, "manual", None)
    second_run = sync_service.run_sync(db_session, client, "manual", None)

    assert second_run.summary["org_units"]["created"] == 0
    assert second_run.summary["org_units"]["unchanged"] == 5
    assert second_run.summary["users"]["created"] == 0
    assert second_run.summary["users"]["unchanged"] == 8

    # Не создаёт дублей
    assert db_session.query(OrgUnit).count() == 5
    assert db_session.query(User).count() == 8
    assert db_session.query(ExternalIdMapping).count() == 13


def test_rerun_detects_field_update(db_session, client, monkeypatch):
    sync_service.run_sync(db_session, client, "manual", None)

    original_fetch = client.fetch_users

    def fetch_users_with_change():
        users = original_fetch()
        users[0].full_name = "Изменённое Имя"
        return users

    monkeypatch.setattr(client, "fetch_users", fetch_users_with_change)

    run = sync_service.run_sync(db_session, client, "manual", None)
    assert run.summary["users"]["updated"] == 1
    assert run.summary["users"]["unchanged"] == 7
