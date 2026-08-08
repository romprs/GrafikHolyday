import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin

_JSON_TYPE = JSON().with_variant(JSONB, "postgresql")

TRIGGER_TYPES = ("scheduled", "manual")
RUN_STATUSES = ("running", "success", "failed", "partial")
CHANGE_TYPES = ("created", "updated", "deactivated", "unchanged")


class SyncRun(UUIDPKMixin, Base):
    __tablename__ = "sync_runs"
    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('scheduled', 'manual')", name="ck_sync_runs_trigger_type"
        ),
        CheckConstraint(
            "status IN ('running', 'success', 'failed', 'partial')", name="ck_sync_runs_status"
        ),
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String, nullable=False)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    summary: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class SyncChangeLog(UUIDPKMixin, Base):
    __tablename__ = "sync_change_log"
    __table_args__ = (
        CheckConstraint(
            "change_type IN ('created', 'updated', 'deactivated', 'unchanged')",
            name="ck_sync_change_log_change_type",
        ),
    )

    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sync_runs.id"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    internal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    change_type: Mapped[str] = mapped_column(String, nullable=False)
    diff: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
