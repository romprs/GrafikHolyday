import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class User(UUIDPKMixin, TimestampMixin, Base):
    """Сотрудник. Данные (кроме локальных ролей) владеет процесс синхронизации."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    # Табельный номер — локальное поле (в отличие от остального, синком не
    # владеет): используется для сопоставления с внешними системами, где
    # сотрудник идентифицируется этим номером, а не email/ФИО (например,
    # источник учебных планов, см. app/integrations/study_periods.py).
    employee_code: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    org_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_units.id"), nullable=True
    )
    has_benefits: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
