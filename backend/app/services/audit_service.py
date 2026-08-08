import uuid

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
