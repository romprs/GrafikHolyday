import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# JSON на SQLite (unit-тесты) — JSONB нативно только для Postgres.
_JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class RestrictionSettings(Base):
    """Управляемые ограничения (мин. длительность, блокировки, пороги загруженности).

    Natural key (не UUID) — записи создаются кодом через сиды, а не пользователем.
    """

    __tablename__ = "restriction_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    params: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )


MIN_LEAVE_DURATION = "min_leave_duration"
BLOCKED_PERIOD_ENFORCEMENT = "blocked_period_enforcement"
DEPARTMENT_LOAD_THRESHOLDS = "department_load_thresholds"
