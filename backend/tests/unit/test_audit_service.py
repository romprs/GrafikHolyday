import uuid
from datetime import date, datetime, timezone

from app.models.audit_log import AuditLog
from app.models.user import User
from app.services import audit_service


def _log_entry(db_session, actor, when: datetime) -> AuditLog:
    entry = AuditLog(
        entity_type="org_unit",
        entity_id=uuid.uuid4(),
        action="update",
        performed_by=actor.id,
        reason="test",
        before_state={},
        after_state={},
        created_at=when,
    )
    db_session.add(entry)
    db_session.flush()
    return entry


def _actor(db_session) -> User:
    user = User(email="actor@test.local", full_name="Actor")
    db_session.add(user)
    db_session.flush()
    return user


def test_clear_without_range_removes_everything(db_session):
    actor = _actor(db_session)
    _log_entry(db_session, actor, datetime(2026, 1, 1, tzinfo=timezone.utc))
    _log_entry(db_session, actor, datetime(2026, 6, 1, tzinfo=timezone.utc))

    deleted = audit_service.clear(db_session, None, None)

    assert deleted == 2
    assert db_session.query(AuditLog).count() == 0


def test_clear_with_range_keeps_entries_outside_it(db_session):
    actor = _actor(db_session)
    _log_entry(db_session, actor, datetime(2026, 1, 15, tzinfo=timezone.utc))
    _log_entry(db_session, actor, datetime(2026, 6, 15, tzinfo=timezone.utc))
    _log_entry(db_session, actor, datetime(2026, 12, 15, tzinfo=timezone.utc))

    deleted = audit_service.clear(db_session, date(2026, 6, 1), date(2026, 6, 30))

    assert deleted == 1
    remaining = {e.created_at.month for e in db_session.query(AuditLog).all()}
    assert remaining == {1, 12}


def test_clear_noop_on_empty_log(db_session):
    assert audit_service.clear(db_session, None, None) == 0
