from datetime import datetime, timedelta, timezone

from app import scheduler
from app.models.sync import KIND_ORG_DIRECTORY, SyncRun


def _add_run(db_session, *, status: str, started_at) -> SyncRun:
    run = SyncRun(kind=KIND_ORG_DIRECTORY, trigger_type="manual", status=status, started_at=started_at)
    db_session.add(run)
    db_session.commit()
    return run


def test_not_due_when_interval_missing_or_non_positive(db_session):
    assert scheduler._is_due(db_session, KIND_ORG_DIRECTORY, None) is False
    assert scheduler._is_due(db_session, KIND_ORG_DIRECTORY, 0) is False
    assert scheduler._is_due(db_session, KIND_ORG_DIRECTORY, -5) is False
    assert scheduler._is_due(db_session, KIND_ORG_DIRECTORY, "60") is False  # не число


def test_due_when_no_prior_run_exists(db_session):
    assert scheduler._is_due(db_session, KIND_ORG_DIRECTORY, 60) is True


def test_not_due_when_last_run_recent(db_session):
    _add_run(
        db_session,
        status="success",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    assert scheduler._is_due(db_session, KIND_ORG_DIRECTORY, 60) is False


def test_due_when_last_run_older_than_interval(db_session):
    _add_run(
        db_session,
        status="success",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=90),
    )
    assert scheduler._is_due(db_session, KIND_ORG_DIRECTORY, 60) is True


def test_not_due_when_currently_running_and_fresh(db_session):
    _add_run(
        db_session,
        status="running",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    assert scheduler._is_due(db_session, KIND_ORG_DIRECTORY, 60) is False


def test_due_when_running_row_is_stale_abandoned(db_session):
    """Бэкенд перезапустили посреди синка — запись осталась в running
    навсегда, если бы не эта защита."""
    _add_run(
        db_session,
        status="running",
        started_at=datetime.now(timezone.utc)
        - timedelta(minutes=scheduler.STALE_RUNNING_AFTER_MINUTES + 5),
    )
    assert scheduler._is_due(db_session, KIND_ORG_DIRECTORY, 60) is True
