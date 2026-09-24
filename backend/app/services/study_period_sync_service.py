import logging
import math
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.study_periods import (
    StudyPeriodEntryDTO,
    StudyPeriodsClient,
    parse_entries,
    parse_flat_entries,
)
from app.models.blocked_period import USER, BlockedPeriod
from app.models.restriction_settings import STUDY_PERIODS_SOURCE
from app.models.sync import KIND_STUDY_PERIODS, SyncChangeLog, SyncRun
from app.models.user import User
from app.services import restriction_settings_service

logger = logging.getLogger(__name__)

STUDY_PERIOD = "study_period"
# Помечает BlockedPeriod, созданные этой интеграцией — чтобы повторный синк
# обновлял/деактивировал те же строки, а не плодил дубли (см. external_ref).
SOURCE = "study_plan"


def build_client(db: Session) -> StudyPeriodsClient | None:
    """None — источник не настроен/выключен/в режиме "файл" (для него
    планировщику/автозапуску нечего делать — ждём ручной загрузки файла)."""
    setting = restriction_settings_service.get(db, STUDY_PERIODS_SOURCE)
    if setting is None or not setting.enabled:
        return None
    params = setting.params
    if params.get("mode") != "http":
        return None
    base_url = params.get("base_url") or ""
    if not base_url:
        return None
    return StudyPeriodsClient(
        base_url=base_url,
        login=params.get("auth_login") or "",
        password=params.get("auth_password") or "",
        verify_tls=bool(params.get("verify_tls", False)),
    )


def _external_ref(entry: StudyPeriodEntryDTO) -> str:
    return f"{entry.employee_code}:{entry.date.isoformat()}:{entry.program_name}"


HOURS_PER_DAY = 8


def _end_date(entry: StudyPeriodEntryDTO) -> date:
    """Раньше блокировался ровно 1 день независимо от продолжительности
    обучения (КолВоЧасов из источника игнорировалось) — многодневный курс
    (например, 16 часов = 2 полных дня) блокировал только первый день,
    и сотрудник мог подать заявку на отпуск на второй день курса. Считаем
    длительность как обычные рабочие дни по 8 часов, минимум 1 день."""
    days = max(1, math.ceil(entry.hours / HOURS_PER_DAY)) if entry.hours > 0 else 1
    return entry.date + timedelta(days=days - 1)


def _apply(
    db: Session,
    entries: list[StudyPeriodEntryDTO],
    employee_errors: dict[str, str],
    trigger_type: str,
    triggered_by: uuid.UUID | None,
) -> SyncRun:
    """Общее ядро для обоих режимов (файл/HTTP) — принимает уже
    распарсенный плоский список записей и приводит недоступные периоды
    сотрудников (BlockedPeriod, scope=user) в соответствие с ним:
    заводит новые, обновляет изменившиеся, деактивирует пропавшие."""
    run = SyncRun(kind=KIND_STUDY_PERIODS, trigger_type=trigger_type, triggered_by=triggered_by, status="running")
    db.add(run)
    db.flush()

    summary: dict = {
        "entries_received": len(entries),
        "employees_matched": 0,
        "employees_unmatched": 0,
        "employees_failed": len(employee_errors),
        "periods_created": 0,
        "periods_updated": 0,
        "periods_unchanged": 0,
        "periods_deactivated": 0,
        "errors": list(employee_errors.values())[:20],
    }

    logger.info(
        "Синхронизация недоступных периодов: начало обработки (run_id=%s, trigger=%s, записей получено=%d, сбоев запроса=%d)",
        run.id,
        trigger_type,
        len(entries),
        len(employee_errors),
    )

    try:
        users_by_code = {
            u.employee_code: u
            for u in db.scalars(select(User).where(User.employee_code.isnot(None))).all()
        }

        by_employee: dict[str, list[StudyPeriodEntryDTO]] = {}
        for entry in entries:
            by_employee.setdefault(entry.employee_code, []).append(entry)

        unmatched_codes: set[str] = set()
        for employee_code, employee_entries in by_employee.items():
            user = users_by_code.get(employee_code)
            if user is None:
                unmatched_codes.add(employee_code)
                continue
            summary["employees_matched"] += 1

            existing = {
                bp.external_ref: bp
                for bp in db.scalars(
                    select(BlockedPeriod).where(
                        BlockedPeriod.external_source == SOURCE, BlockedPeriod.user_id == user.id
                    )
                ).all()
            }
            seen_refs: set[str] = set()
            for entry in employee_entries:
                ref = _external_ref(entry)
                seen_refs.add(ref)
                row = existing.get(ref)
                entry_date_to = _end_date(entry)
                if row is None:
                    row = BlockedPeriod(
                        date_from=entry.date,
                        date_to=entry_date_to,
                        reason=entry.program_name,
                        scope=USER,
                        user_id=user.id,
                        external_source=SOURCE,
                        external_ref=ref,
                        created_by=triggered_by,
                        is_active=True,
                    )
                    db.add(row)
                    db.flush()
                    summary["periods_created"] += 1
                    change_type = "created"
                elif not row.is_active or row.reason != entry.program_name or row.date_to != entry_date_to:
                    row.is_active = True
                    row.reason = entry.program_name
                    row.date_to = entry_date_to
                    summary["periods_updated"] += 1
                    change_type = "updated"
                else:
                    summary["periods_unchanged"] += 1
                    change_type = "unchanged"
                db.add(
                    SyncChangeLog(
                        sync_run_id=run.id,
                        entity_type=STUDY_PERIOD,
                        external_id=ref,
                        internal_id=row.id,
                        change_type=change_type,
                        diff={},
                    )
                )

            for ref, row in existing.items():
                if ref not in seen_refs and row.is_active:
                    row.is_active = False
                    summary["periods_deactivated"] += 1
                    db.add(
                        SyncChangeLog(
                            sync_run_id=run.id,
                            entity_type=STUDY_PERIOD,
                            external_id=ref,
                            internal_id=row.id,
                            change_type="deactivated",
                            diff={},
                        )
                    )

        summary["employees_unmatched"] = len(unmatched_codes)
        if unmatched_codes:
            summary["unmatched_employee_codes"] = sorted(unmatched_codes)[:20]

        if employee_errors and not by_employee:
            run.status = "failed"
        elif employee_errors or unmatched_codes:
            run.status = "partial"
        else:
            run.status = "success"

        logger.info(
            "Синхронизация недоступных периодов: завершена (run_id=%s), статус=%s, сводка: %s",
            run.id,
            run.status,
            summary,
        )
    except Exception as exc:  # noqa: BLE001 — фиксируем любую ошибку синка в run, не роняем процесс
        run.status = "failed"
        run.error_message = str(exc)
        logger.exception("Синхронизация недоступных периодов завершилась ошибкой (run_id=%s)", run.id)

    run.summary = summary
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run


def run_file_import(
    db: Session, raw: list[dict], trigger_type: str, triggered_by: uuid.UUID
) -> SyncRun:
    entries = parse_entries(raw)
    return _apply(db, entries, {}, trigger_type, triggered_by)


def run_http_sync(
    db: Session,
    client: StudyPeriodsClient,
    period_from: date,
    period_to: date,
    trigger_type: str,
    triggered_by: uuid.UUID | None,
) -> SyncRun:
    users = list(
        db.scalars(select(User).where(User.employee_code.isnot(None), User.is_active)).all()
    )
    logger.info(
        "Синхронизация недоступных периодов: начало HTTP-синка (trigger=%s, период=%s..%s, сотрудников с табельным номером=%d)",
        trigger_type,
        period_from,
        period_to,
        len(users),
    )
    entries: list[StudyPeriodEntryDTO] = []
    errors: dict[str, str] = {}
    for user in users:
        try:
            raw = client.fetch_raw(user.employee_code, period_from, period_to)
        except Exception as exc:  # noqa: BLE001 — один сбойный сотрудник не должен рвать весь синк
            errors[user.employee_code] = f"{user.employee_code}: {exc}"
            logger.warning(
                "Синхронизация недоступных периодов: сбой запроса по табельному номеру %s: %s",
                user.employee_code,
                exc,
            )
            continue
        try:
            # Разбираем сразу, пока табельный номер ещё в контексте — ответ
            # источника плоский и его самого не содержит (см. parse_flat_entries).
            entries.extend(parse_flat_entries(user.employee_code, raw))
        except Exception as exc:  # noqa: BLE001 — формат ответа не совпал с ожидаемым для этого сотрудника
            errors[user.employee_code] = f"{user.employee_code}: ответ не разобран: {exc}"
            logger.warning(
                "Синхронизация недоступных периодов: не удалось разобрать ответ по табельному номеру %s: %s",
                user.employee_code,
                exc,
            )
    logger.info(
        "Синхронизация недоступных периодов: HTTP-запросы завершены (trigger=%s), разобрано записей=%d, сбоев=%d из %d",
        trigger_type,
        len(entries),
        len(errors),
        len(users),
    )
    return _apply(db, entries, errors, trigger_type, triggered_by)
