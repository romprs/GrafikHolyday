import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


def log(
    db: Session,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    performed_by: User,
    reason: str,
    before_state: dict,
    after_state: dict,
) -> None:
    db.add(
        AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            performed_by=performed_by.id,
            reason=reason,
            before_state=before_state,
            after_state=after_state,
        )
    )


def clear(db: Session, date_from: date | None, date_to: date | None) -> int:
    """Чистка журнала за период (обе границы включительно) — без указания
    границ чистит весь журнал целиком. Сама по себе не логируется — журнал
    аудита не аудирует собственную очистку, как и история синхронизаций."""
    query = delete(AuditLog)
    if date_from is not None:
        query = query.where(AuditLog.created_at >= datetime.combine(date_from, time.min, timezone.utc))
    if date_to is not None:
        query = query.where(AuditLog.created_at <= datetime.combine(date_to, time.max, timezone.utc))
    deleted = db.execute(query).rowcount
    db.commit()
    return deleted
