import uuid

import pytest

from app.integrations.vacation_days import VacationDaysEntryDTO
from app.models.leave_balance import LeaveBalance
from app.models.user import User
from app.services import vacation_days_sync_service


class StubClient:
    def __init__(self, by_tabnum: dict[str, VacationDaysEntryDTO | None]):
        self._by_tabnum = by_tabnum
        self.calls: list[str] = []

    def fetch(self, tabnum: str) -> VacationDaysEntryDTO | None:
        self.calls.append(tabnum)
        if tabnum not in self._by_tabnum:
            raise RuntimeError("boom")
        return self._by_tabnum[tabnum]


@pytest.fixture()
def employee(db_session):
    user = User(email="e@test.local", full_name="Employee", employee_code="6378")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture()
def hr_admin_id():
    return uuid.uuid4()


def test_creates_balance_and_sets_benefits(db_session, employee, hr_admin_id):
    client = StubClient({"6378": VacationDaysEntryDTO(days_count=36, is_beneficiary=True)})
    run = vacation_days_sync_service.run_sync(db_session, client, 2026, "manual", hr_admin_id)

    assert run.status == "success"
    assert run.summary["balances_created"] == 1
    assert run.summary["benefits_changed"] == 1

    db_session.refresh(employee)
    assert employee.has_benefits is True
    balance = db_session.query(LeaveBalance).filter_by(user_id=employee.id, year=2026).one()
    assert float(balance.accrued_days) == 36


def test_idempotent_on_second_run(db_session, employee, hr_admin_id):
    client = StubClient({"6378": VacationDaysEntryDTO(days_count=36, is_beneficiary=False)})
    vacation_days_sync_service.run_sync(db_session, client, 2026, "manual", hr_admin_id)
    second = vacation_days_sync_service.run_sync(db_session, client, 2026, "manual", hr_admin_id)

    assert second.summary["balances_unchanged"] == 1
    assert second.summary["balances_created"] == 0


def test_updates_existing_balance(db_session, employee, hr_admin_id):
    client = StubClient({"6378": VacationDaysEntryDTO(days_count=28, is_beneficiary=False)})
    vacation_days_sync_service.run_sync(db_session, client, 2026, "manual", hr_admin_id)

    client2 = StubClient({"6378": VacationDaysEntryDTO(days_count=44, is_beneficiary=False)})
    run = vacation_days_sync_service.run_sync(db_session, client2, 2026, "manual", hr_admin_id)

    assert run.summary["balances_updated"] == 1
    balance = db_session.query(LeaveBalance).filter_by(user_id=employee.id, year=2026).one()
    assert float(balance.accrued_days) == 44


def test_does_not_touch_carried_over_days(db_session, employee, hr_admin_id):
    db_session.add(LeaveBalance(user_id=employee.id, year=2026, accrued_days=20, carried_over_days=5))
    db_session.flush()

    client = StubClient({"6378": VacationDaysEntryDTO(days_count=36, is_beneficiary=False)})
    vacation_days_sync_service.run_sync(db_session, client, 2026, "manual", hr_admin_id)

    balance = db_session.query(LeaveBalance).filter_by(user_id=employee.id, year=2026).one()
    assert float(balance.accrued_days) == 36
    assert float(balance.carried_over_days) == 5


def test_no_data_response_is_skipped_not_partial(db_session, employee, hr_admin_id):
    client = StubClient({"6378": None})
    run = vacation_days_sync_service.run_sync(db_session, client, 2026, "manual", hr_admin_id)

    assert run.status == "success"
    assert run.summary["employees_no_data"] == 1
    assert db_session.query(LeaveBalance).count() == 0


def test_all_employees_failing_marks_run_failed(db_session, employee, hr_admin_id):
    client = StubClient({})  # ни один tabnum не настроен -> raises для всех
    run = vacation_days_sync_service.run_sync(db_session, client, 2026, "manual", hr_admin_id)

    assert run.status == "failed"  # единственный сотрудник и тот упал
    assert run.summary["employees_failed"] == 1


def test_partial_status_when_some_employees_fail(db_session, employee, hr_admin_id):
    other = User(email="other@test.local", full_name="Other", employee_code="1000")
    db_session.add(other)
    db_session.flush()

    client = StubClient({"6378": VacationDaysEntryDTO(days_count=36, is_beneficiary=False)})
    run = vacation_days_sync_service.run_sync(db_session, client, 2026, "manual", hr_admin_id)

    assert run.status == "partial"
    assert run.summary["employees_failed"] == 1
    assert run.summary["balances_created"] == 1
