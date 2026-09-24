import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.vacation_days import VacationDaysClient
from app.models.leave_balance import LeaveBalance
from app.models.restriction_settings import VACATION_DAYS_SOURCE
from app.models.sync import KIND_VACATION_DAYS, SyncChangeLog, SyncRun
from app.models.user import User
from app.services import restriction_settings_service

logger = logging.getLogger(__name__)

VACATION_DAYS_ENTITY = "vacation_days"


def build_client(db: Session) -> VacationDaysClient | None:
    """None — источник не настроен/выключен, вызывающая сторона решает, что
    делать (роутер — вернуть ошибку пользователю, планировщик — тихо
    пропустить цикл)."""
    setting = restriction_settings_service.get(db, VACATION_DAYS_SOURCE)
    if setting is None or not setting.enabled:
        return None
    base_url = setting.params.get("base_url") or ""
    if not base_url:
        return None
    return VacationDaysClient(
        base_url=base_url,
        login=setting.params.get("auth_login") or "",
        password=setting.params.get("auth_password") or "",
        verify_tls=bool(setting.params.get("verify_tls", False)),
    )


def run_sync(
    db: Session,
    client: VacationDaysClient,
    year: int,
    trigger_type: str,
    triggered_by: uuid.UUID | None,
) -> SyncRun:
    """Остаток дней отпуска и признак льготника — отдельный источник от
    оргструктуры/сотрудников, запрашивается по одному табельному номеру за
    раз (см. app/integrations/vacation_days.py). carried_over_days (перенос
    с прошлого года) этим синком не трогается — его по-прежнему проставляет
    HR вручную (см. leave_balance_service.set_balance)."""
    run = SyncRun(
        kind=KIND_VACATION_DAYS, trigger_type=trigger_type, triggered_by=triggered_by, status="running"
    )
    db.add(run)
    db.flush()

    summary: dict = {
        "employees_checked": 0,
        "employees_failed": 0,
        "employees_no_data": 0,
        "balances_created": 0,
        "balances_updated": 0,
        "balances_unchanged": 0,
        "benefits_changed": 0,
        "errors": [],
    }

    users = list(
        db.scalars(select(User).where(User.employee_code.isnot(None), User.is_active)).all()
    )
    logger.info(
        "Синхронизация дней отпуска: начало (run_id=%s, trigger=%s), сотрудников к проверке=%d",
        run.id,
        trigger_type,
        len(users),
    )

    for user in users:
        summary["employees_checked"] += 1
        try:
            entry = client.fetch(user.employee_code)
        except Exception as exc:  # noqa: BLE001 — один сбойный сотрудник не должен рвать весь синк
            summary["employees_failed"] += 1
            summary["errors"].append(f"{user.employee_code}: {exc}")
            logger.warning(
                "Синхронизация дней отпуска: сбой запроса по табельному номеру %s (run_id=%s): %s",
                user.employee_code,
                run.id,
                exc,
            )
            continue

        if entry is None:
            summary["employees_no_data"] += 1
            continue

        if user.has_benefits != entry.is_beneficiary:
            user.has_benefits = entry.is_beneficiary
            summary["benefits_changed"] += 1

        # Источник может прислать пустое значение (ещё не заполнено на его
        # стороне) — не затираем уже известную дату None'ом, только
        # обновляем, когда реально пришло значение (та же логика, что и у
        # employee_code в sync_service._resolve_employee_code).
        if entry.hire_date is not None:
            user.hire_date = entry.hire_date
        if entry.termination_date is not None:
            user.termination_date = entry.termination_date

        balance = db.scalar(
            select(LeaveBalance).where(LeaveBalance.user_id == user.id, LeaveBalance.year == year)
        )
        if balance is None:
            balance = LeaveBalance(user_id=user.id, year=year, accrued_days=entry.days_count)
            db.add(balance)
            db.flush()
            change_type = "created"
            summary["balances_created"] += 1
        elif float(balance.accrued_days) != entry.days_count:
            balance.accrued_days = entry.days_count
            change_type = "updated"
            summary["balances_updated"] += 1
        else:
            change_type = "unchanged"
            summary["balances_unchanged"] += 1

        db.add(
            SyncChangeLog(
                sync_run_id=run.id,
                entity_type=VACATION_DAYS_ENTITY,
                external_id=user.employee_code,
                internal_id=user.id,
                change_type=change_type,
                diff={},
            )
        )

    if users and summary["employees_failed"] == len(users):
        run.status = "failed"
    elif summary["employees_failed"]:
        run.status = "partial"
    else:
        run.status = "success"

    logger.info(
        "Синхронизация дней отпуска: завершена (run_id=%s), статус=%s, сводка: %s",
        run.id,
        run.status,
        summary,
    )
    run.summary = summary
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run
