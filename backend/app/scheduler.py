"""Автозапуск синхронизаций по расписанию (poll_interval_minutes в
настройках источника) — до этой фичи всё запускалось только вручную
кнопкой в UI.

uvicorn у нас поднимается с --workers 2 (см. deploy/redos8/vacation-backend.
service) — если наивно завести APScheduler на старте приложения, каждый из
двух воркеров запустит свой планировщик, и каждый цикл проверки будет
выполняться дважды почти одновременно (двойная синхронизация, лишняя
нагрузка на внешние системы). Защита — advisory lock Postgres
(pg_try_advisory_lock): в конкретный момент проверку реально выполняет
только тот воркер, который успел взять лок, второй просто выходит без
работы. На SQLite (юнит-тесты, локальная разработка) advisory lock
недоступен — там просто пропускаем блокировку (единственный процесс, гонки
не бывает).
"""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.restriction_settings import (
    EXTERNAL_SOURCE_CONNECTION,
    STUDY_PERIODS_SOURCE,
    VACATION_DAYS_SOURCE,
)
from app.models.sync import KIND_ORG_DIRECTORY, KIND_STUDY_PERIODS, KIND_VACATION_DAYS, SyncRun
from app.services import (
    restriction_settings_service,
    study_period_sync_service,
    sync_service,
    vacation_days_sync_service,
)

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60
# Если запись "running" висит дольше этого срока — считаем её брошенной
# (бэкенд перезапустили посреди синка) и разрешаем новый запуск, а не ждём
# вечно строку, которую уже некому закрыть.
STALE_RUNNING_AFTER_MINUTES = 30
# Фиксированный ключ приложения для pg_advisory_lock — произвольное число,
# важно только что оно не пересекается с другими использованиями advisory
# lock в этой БД (сейчас таких больше нет).
ADVISORY_LOCK_KEY = 917_263_401


def _as_utc(value: datetime) -> datetime:
    """SQLite (юнит-тесты) не хранит tzinfo даже для DateTime(timezone=True)
    и отдаёт наивные datetime обратно — а они были записаны как UTC (см.
    server_default=func.now()), поэтому наивность здесь всегда означает UTC.
    Postgres в проде уже отдаёт aware datetime, этот случай трогать не нужно."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _is_due(db: Session, kind: str, interval_minutes: object) -> bool:
    if not isinstance(interval_minutes, (int, float)) or interval_minutes <= 0:
        return False

    latest = db.scalar(
        select(SyncRun).where(SyncRun.kind == kind).order_by(SyncRun.started_at.desc()).limit(1)
    )
    if latest is None:
        return True
    started_at = _as_utc(latest.started_at)
    if latest.status == "running":
        age = datetime.now(timezone.utc) - started_at
        if age < timedelta(minutes=STALE_RUNNING_AFTER_MINUTES):
            return False
        logger.warning(
            "Планировщик: запись синхронизации %s (kind=%s) висит в статусе running дольше %d "
            "минут — считаю брошенной (вероятно, бэкенд перезапустили посреди синка) и запускаю новую",
            latest.id,
            kind,
            STALE_RUNNING_AFTER_MINUTES,
        )
        return True
    return datetime.now(timezone.utc) - started_at >= timedelta(minutes=interval_minutes)


def _run_org_directory_if_due(db: Session) -> None:
    setting = restriction_settings_service.get(db, EXTERNAL_SOURCE_CONNECTION)
    if setting is None or not setting.enabled:
        return
    if not _is_due(db, KIND_ORG_DIRECTORY, setting.params.get("poll_interval_minutes")):
        return
    logger.info("Планировщик: запускаю синхронизацию оргструктуры по расписанию")
    client = sync_service.build_client(db)
    sync_service.run_sync(db, client, trigger_type="scheduled", triggered_by=None)


def _run_study_periods_if_due(db: Session) -> None:
    from datetime import date

    setting = restriction_settings_service.get(db, STUDY_PERIODS_SOURCE)
    if setting is None or not setting.enabled:
        return
    if not _is_due(db, KIND_STUDY_PERIODS, setting.params.get("poll_interval_minutes")):
        return
    client = study_period_sync_service.build_client(db)
    if client is None:
        return
    logger.info("Планировщик: запускаю синхронизацию недоступных периодов по расписанию")
    year = restriction_settings_service.get_planning_year(db)
    study_period_sync_service.run_http_sync(
        db, client, date(year, 1, 1), date(year, 12, 31), "scheduled", None
    )


def _run_vacation_days_if_due(db: Session) -> None:
    setting = restriction_settings_service.get(db, VACATION_DAYS_SOURCE)
    if setting is None or not setting.enabled:
        return
    if not _is_due(db, KIND_VACATION_DAYS, setting.params.get("poll_interval_minutes")):
        return
    client = vacation_days_sync_service.build_client(db)
    if client is None:
        return
    logger.info("Планировщик: запускаю синхронизацию дней отпуска и льгот по расписанию")
    year = restriction_settings_service.get_planning_year(db)
    vacation_days_sync_service.run_sync(db, client, year, "scheduled", None)


def _check_all() -> None:
    db = SessionLocal()
    try:
        is_postgres = db.bind.dialect.name == "postgresql"
        if is_postgres:
            got_lock = db.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY}
            ).scalar()
            if not got_lock:
                return
        try:
            for job in (_run_org_directory_if_due, _run_study_periods_if_due, _run_vacation_days_if_due):
                try:
                    job(db)
                except Exception:  # noqa: BLE001 — сбой одной интеграции не должен снимать лок/останавливать остальные
                    logger.exception("Планировщик: ошибка при проверке/запуске %s", job.__name__)
        finally:
            if is_postgres:
                db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY})
    finally:
        db.close()


_scheduler: BackgroundScheduler | None = None


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_check_all, "interval", seconds=CHECK_INTERVAL_SECONDS, id="sync-scheduler")
    _scheduler.start()
    logger.info(
        "Планировщик синхронизаций запущен (проверка каждые %d с; фактический запуск — по "
        "poll_interval_minutes каждого источника в настройках)",
        CHECK_INTERVAL_SECONDS,
    )


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
