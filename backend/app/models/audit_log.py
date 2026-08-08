import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin

_JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class AuditLog(UUIDPKMixin, Base):
    """Общий (не только для заявок) журнал изменений задним числом —
    entity_type/entity_id вместо отдельной таблицы на каждую сущность,
    чтобы сюда же позже легло логирование правок blocked_periods,
    restriction_settings и т.п. без новой миграции."""

    __tablename__ = "audit_log"

    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    performed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    before_state: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False, default=dict)
    after_state: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
