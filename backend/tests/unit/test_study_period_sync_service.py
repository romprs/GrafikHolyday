import uuid

import pytest

from app.models.blocked_period import BlockedPeriod
from app.models.user import User
from app.services import study_period_sync_service


@pytest.fixture()
def employee(db_session):
    user = User(email="e@test.local", full_name="Employee", employee_code="2800")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture()
def hr_admin_id():
    return uuid.uuid4()


RAW = [
    {
        "2800": [
            {"ПрограммаОбучения": "Курс Python", "Дата": "24.10.2026 0:00:00", "КолВоЧасов": "16"},
            {"ПрограммаОбучения": "Курс SQL", "Дата": "25.10.2026 0:00:00", "КолВоЧасов": "8"},
        ]
    }
]


def test_file_import_creates_blocked_periods(db_session, employee, hr_admin_id):
    run = study_period_sync_service.run_file_import(db_session, RAW, "manual", hr_admin_id)

    assert run.status == "success"
    assert run.summary["periods_created"] == 2
    periods = db_session.query(BlockedPeriod).filter_by(user_id=employee.id).all()
    assert len(periods) == 2
    assert all(p.scope == "user" and p.is_active for p in periods)


def test_file_import_is_idempotent(db_session, employee, hr_admin_id):
    study_period_sync_service.run_file_import(db_session, RAW, "manual", hr_admin_id)
    second = study_period_sync_service.run_file_import(db_session, RAW, "manual", hr_admin_id)

    assert second.summary["periods_created"] == 0
    assert second.summary["periods_unchanged"] == 2
    assert db_session.query(BlockedPeriod).count() == 2


def test_file_import_deactivates_removed_entries(db_session, employee, hr_admin_id):
    study_period_sync_service.run_file_import(db_session, RAW, "manual", hr_admin_id)

    shorter_raw = [{"2800": [RAW[0]["2800"][0]]}]
    run = study_period_sync_service.run_file_import(db_session, shorter_raw, "manual", hr_admin_id)

    assert run.summary["periods_deactivated"] == 1
    active = db_session.query(BlockedPeriod).filter_by(user_id=employee.id, is_active=True).all()
    assert len(active) == 1


def test_file_import_unmatched_employee_code_is_partial(db_session, hr_admin_id):
    run = study_period_sync_service.run_file_import(db_session, RAW, "manual", hr_admin_id)

    assert run.status == "partial"
    assert run.summary["employees_unmatched"] == 1
    assert db_session.query(BlockedPeriod).count() == 0
