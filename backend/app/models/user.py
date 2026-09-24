import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
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
    # Дата приёма и увольнения — из того же источника 1С, что и дни отпуска
    # (см. app/integrations/vacation_days.py). Нужны для ограничения на
    # выплату ЕСВ по стажу (см. validation/vacation_bonus_tenure_rule.py).
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Право согласовывать заявки своего подразделения независимо от того,
    # является ли сотрудник head_user_id юнита (см. permissions/approval_service) —
    # для замещения руководителя (например, во время его отсутствия) без
    # переназначения самого head_user_id. У фактических руководителей право
    # согласования и так есть через head_user_id — этот флаг только
    # РАСШИРЯЕТ круг согласующих, не сужает его.
    is_approver: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
