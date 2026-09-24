import uuid
from datetime import date

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


def test_multi_day_training_blocks_more_than_one_day(db_session, employee, hr_admin_id):
    """16 часов обучения — 2 полных рабочих дня (по 8ч), а не 1 день, как
    было раньше (КолВоЧасов из источника игнорировалось)."""
    raw = [
        {
            "2800": [
                {"ПрограммаОбучения": "Курс Python", "Дата": "24.10.2026 0:00:00", "КолВоЧасов": "16"},
            ]
        }
    ]
    run = study_period_sync_service.run_file_import(db_session, raw, "manual", hr_admin_id)

    assert run.summary["periods_created"] == 1
    period = db_session.query(BlockedPeriod).filter_by(user_id=employee.id).one()
    assert period.date_from == date(2026, 10, 24)
    assert period.date_to == date(2026, 10, 25)


def test_updated_training_duration_extends_existing_period(db_session, employee, hr_admin_id):
    raw_short = [{"2800": [{"ПрограммаОбучения": "Курс Python", "Дата": "24.10.2026 0:00:00", "КолВоЧасов": "8"}]}]
    study_period_sync_service.run_file_import(db_session, raw_short, "manual", hr_admin_id)

    raw_longer = [{"2800": [{"ПрограммаОбучения": "Курс Python", "Дата": "24.10.2026 0:00:00", "КолВоЧасов": "24"}]}]
    run = study_period_sync_service.run_file_import(db_session, raw_longer, "manual", hr_admin_id)

    assert run.summary["periods_updated"] == 1
    period = db_session.query(BlockedPeriod).filter_by(user_id=employee.id).one()
    assert period.date_to == date(2026, 10, 26)


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


class _FakeHttpClient:
    """Реальный формат ответа источника — плоский список без обёртки по
    табельному номеру, ключ "ПрограмаОбучения" с одной "м", дата ISO 8601."""

    def __init__(self, by_employee: dict[str, list[dict]]):
        self._by_employee = by_employee

    def fetch_raw(self, employee_code: str, period_from: date, period_to: date) -> list[dict]:
        if employee_code not in self._by_employee:
            raise RuntimeError("сотрудник не найден в источнике")
        return self._by_employee[employee_code]


def test_http_sync_parses_real_flat_response_format(db_session, employee, hr_admin_id):
    client = _FakeHttpClient(
        {
            "2800": [
                {"ПрограмаОбучения": "Заявка на обучение 2027 г", "Дата": "2027-01-01T00:00:00", "КолВоЧасов": 16},
                {
                    "ПрограмаОбучения": "Оказание первой помощи пострадавшим на производстве",
                    "Дата": "2027-06-17T00:00:00",
                    "КолВоЧасов": 15,
                },
            ]
        }
    )

    run = study_period_sync_service.run_http_sync(
        db_session, client, date(2027, 1, 1), date(2027, 12, 31), "manual", hr_admin_id
    )

    assert run.status == "success"
    assert run.summary["periods_created"] == 2
    periods = db_session.query(BlockedPeriod).filter_by(user_id=employee.id).all()
    assert len(periods) == 2


def test_http_sync_records_per_employee_parse_error_without_failing_whole_run(
    db_session, employee, hr_admin_id
):
    client = _FakeHttpClient({"2800": [{"unexpected": "shape"}]})

    run = study_period_sync_service.run_http_sync(
        db_session, client, date(2027, 1, 1), date(2027, 12, 31), "manual", hr_admin_id
    )

    assert run.status == "failed"
    assert run.summary["employees_failed"] == 1
    assert db_session.query(BlockedPeriod).count() == 0
