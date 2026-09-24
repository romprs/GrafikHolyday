import pytest
from sqlalchemy import select

from app.models.external_id_mapping import ExternalIdMapping
from app.models.org_unit import OrgUnit
from app.models.sync import KIND_ORG_DIRECTORY, KIND_STUDY_PERIODS, SyncChangeLog, SyncRun
from app.models.user import User
from app.services import sync_service
from app.sync.dto import ExternalUserDTO
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


def test_has_benefits_none_preserves_existing_value(db_session, client, monkeypatch):
    """Источник (например, справочник отделов/сотрудников) может не знать
    льготность — has_benefits=None не должен затирать значение, выставленное
    отдельным синком (vacation_days) или HR вручную."""
    sync_service.run_sync(db_session, client, "manual", None)

    target = db_session.query(User).filter_by(email="backend.head@example.com").one()
    target.has_benefits = True
    db_session.commit()

    original_fetch = client.fetch_users

    def fetch_users_with_unknown_benefits():
        users = original_fetch()
        for u in users:
            u.has_benefits = None
        return users

    monkeypatch.setattr(client, "fetch_users", fetch_users_with_unknown_benefits)
    sync_service.run_sync(db_session, client, "manual", None)

    db_session.refresh(target)
    assert target.has_benefits is True


def test_employee_code_synced_and_not_overwritten_on_clash(db_session):
    class CodedClient(FakeDirectoryClient):
        def fetch_users(self):
            users = super().fetch_users()
            for i, u in enumerate(users):
                u.employee_code = f"T{i:03d}"
            return users

    client = CodedClient()
    sync_service.run_sync(db_session, client, "manual", None)

    user = db_session.query(User).filter_by(email="backend.head@example.com").one()
    assert user.employee_code == "T000"


def test_users_only_sync_resolves_org_unit_synced_in_a_previous_run(db_session, client):
    """Баг из продакшена: загрузка файлом только сотрудников (без
    подразделений) обнуляла org_unit_id у всех сотрудников, хотя
    подразделения уже были заведены предыдущим синком — org_unit_ids
    строился только из ТЕКУЩЕЙ выгрузки. Ссылка должна резолвиться через
    уже существующий маппинг."""
    sync_service.run_sync(db_session, client, "manual", None)

    class UsersOnlyClient(FakeDirectoryClient):
        def fetch_org_units(self):
            return []

    run = sync_service.run_sync(db_session, UsersOnlyClient(), "manual", None)
    assert run.status == "success"

    head = db_session.query(User).filter_by(email="backend.head@example.com").one()
    dept = db_session.query(OrgUnit).filter_by(name="Отдел бэкенда").one()
    assert head.org_unit_id == dept.id


def test_org_units_only_sync_resolves_head_synced_in_a_previous_run(db_session, client):
    """Тот же класс бага в обратную сторону: синк только подразделений
    (без сотрудников) не должен обнулять head_user_id, если руководитель
    уже был заведён предыдущим синком сотрудников."""
    sync_service.run_sync(db_session, client, "manual", None)

    class OrgUnitsOnlyClient(FakeDirectoryClient):
        def fetch_users(self):
            return []

    run = sync_service.run_sync(db_session, OrgUnitsOnlyClient(), "manual", None)
    assert run.status == "success"

    dept = db_session.query(OrgUnit).filter_by(name="Отдел бэкенда").one()
    head = db_session.query(User).filter_by(email="backend.head@example.com").one()
    assert dept.head_user_id == head.id


def test_user_with_changed_external_id_reconciled_by_email(db_session, client):
    """Баг из продакшена: источник переприсвоил внешний ID тому же реальному
    сотруднику (тот же email) — синк выдавал этому external_id свежий
    internal_id и падал на UniqueViolation по users_email_key при попытке
    вставить дубликат, роняя ВЕСЬ синк (3900 сотрудников) на одной записи."""
    sync_service.run_sync(db_session, client, "manual", None)
    original_count = db_session.query(User).count()
    head = db_session.query(User).filter_by(email="backend.head@example.com").one()
    original_id = head.id

    class RenumberedIdClient(FakeDirectoryClient):
        def fetch_users(self):
            users = super().fetch_users()
            for u in users:
                if u.email == "backend.head@example.com":
                    u.external_id = "new-ext-id-after-rehire"
            return users

    run = sync_service.run_sync(db_session, RenumberedIdClient(), "manual", None)

    assert run.status == "success"
    # Не создался дубль — то же количество пользователей, что и было
    assert db_session.query(User).count() == original_count
    reconciled = db_session.query(User).filter_by(email="backend.head@example.com").one()
    assert reconciled.id == original_id

    mapping = db_session.scalar(
        select(ExternalIdMapping).where(
            ExternalIdMapping.entity_type == "user",
            ExternalIdMapping.external_id == "new-ext-id-after-rehire",
        )
    )
    assert mapping is not None
    assert mapping.internal_id == original_id


def test_failed_sync_leaves_session_usable_for_next_run(db_session, client, monkeypatch):
    """Баг из продакшена: сбой (например, IntegrityError на flush) оставлял
    сессию в состоянии "rolled back", и попытка записать run.status="failed"
    и закоммитить сама падала повторно (PendingRollbackError) — вместо
    чистого статуса ошибки клиент получал голый 500. run должен переживать
    rollback (коммитится отдельно до основной работы), а сессия — оставаться
    пригодной для следующего вызова."""

    def boom(*args, **kwargs):
        raise RuntimeError("симулированный сбой БД")

    monkeypatch.setattr(sync_service, "_diff_fields", boom)

    run = sync_service.run_sync(db_session, client, "manual", None)
    assert run.status == "failed"
    assert "симулированный сбой БД" in run.error_message

    # Сессия не "отравлена" — следующий обычный вызов должен отработать как ни в чём не бывало
    monkeypatch.undo()
    second_run = sync_service.run_sync(db_session, client, "manual", None)
    assert second_run.status == "success"


def test_sync_does_not_reactivate_manually_deactivated_org_unit(db_session, client):
    """Баг из продакшена: синк безусловно ставил org_unit.is_active=True на
    каждый прогон — отменяя деактивацию, которую HR сделал вручную через
    админку, хотя источник вообще не отдаёт признак активности
    подразделений (сам факт есть в выгрузке ничего не говорит про is_active)."""
    sync_service.run_sync(db_session, client, "manual", None)

    dept = db_session.query(OrgUnit).filter_by(name="Отдел бэкенда").one()
    dept.is_active = False
    db_session.commit()

    sync_service.run_sync(db_session, client, "manual", None)

    db_session.refresh(dept)
    assert dept.is_active is False


def test_sync_does_not_reactivate_manually_deactivated_user(db_session, client):
    """Тот же баг для сотрудников: HR отключил вручную (или сотрудника
    уволили прошлым синком), а источник всё ещё отдаёт is_active=True для
    него (не успел обновиться/не знает о локальной причине) — следующий
    синк не должен молча включать его обратно."""
    sync_service.run_sync(db_session, client, "manual", None)

    user = db_session.query(User).filter_by(email="backend.head@example.com").one()
    user.is_active = False
    db_session.commit()

    sync_service.run_sync(db_session, client, "manual", None)

    db_session.refresh(user)
    assert user.is_active is False


def test_sync_still_deactivates_user_when_source_reports_departure(db_session, client, monkeypatch):
    """В обратную сторону фикс не должен ломать: если сотрудник СЕЙЧАС
    активен, а источник сообщает об увольнении (is_active=False) — синк
    обязан применить это немедленно, а не игнорировать."""
    sync_service.run_sync(db_session, client, "manual", None)

    original_fetch = client.fetch_users

    def fetch_with_departure():
        users = original_fetch()
        for u in users:
            if u.email == "backend.head@example.com":
                u.is_active = False
        return users

    monkeypatch.setattr(client, "fetch_users", fetch_with_departure)
    sync_service.run_sync(db_session, client, "manual", None)

    user = db_session.query(User).filter_by(email="backend.head@example.com").one()
    assert user.is_active is False


def test_reference_to_never_synced_entity_resolves_to_none(db_session):
    """Ссылка на сущность, которая никогда не синкалась ни этим, ни
    прошлым запуском (а не просто отсутствует в текущей выгрузке) —
    остаётся None, а не роняет синк FK-ошибкой."""

    class DanglingRefClient(FakeDirectoryClient):
        def fetch_org_units(self):
            return []

    run = sync_service.run_sync(db_session, DanglingRefClient(), "manual", None)
    assert run.status == "success"

    head = db_session.query(User).filter_by(email="backend.head@example.com").one()
    assert head.org_unit_id is None


def test_clear_history_removes_runs_and_change_log_only_for_that_kind(db_session, client):
    sync_service.run_sync(db_session, client, "manual", None)
    other_kind_run = SyncRun(kind=KIND_STUDY_PERIODS, trigger_type="manual", status="success")
    db_session.add(other_kind_run)
    db_session.flush()

    deleted = sync_service.clear_history(db_session, KIND_ORG_DIRECTORY)

    assert deleted == 1
    assert db_session.query(SyncRun).filter_by(kind=KIND_ORG_DIRECTORY).count() == 0
    assert db_session.query(SyncChangeLog).count() == 0
    # Другой вид синхронизации не задет.
    assert db_session.query(SyncRun).filter_by(kind=KIND_STUDY_PERIODS).count() == 1


def test_clear_history_noop_when_nothing_to_delete(db_session):
    assert sync_service.clear_history(db_session, KIND_ORG_DIRECTORY) == 0
