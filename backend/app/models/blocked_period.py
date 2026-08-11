import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin

SCOPES = ("global", "org_unit", "user")
_scopes_sql_list = ", ".join(f"'{s}'" for s in SCOPES)

GLOBAL = "global"
ORG_UNIT = "org_unit"
USER = "user"


class BlockedPeriod(UUIDPKMixin, Base):
    """Недоступный для отпуска период (учёба, сборы и т.п.).

    Блокировка на org_unit распространяется на все дочерние подразделения —
    та же логика обхода дерева, что и в расчёте загруженности отдела.
    """

    __tablename__ = "blocked_periods"
    __table_args__ = (
        CheckConstraint(f"scope IN ({_scopes_sql_list})", name="ck_blocked_periods_scope"),
        CheckConstraint("date_to >= date_from", name="ck_blocked_periods_date_order"),
        CheckConstraint(
            "(scope = 'global' AND org_unit_id IS NULL AND user_id IS NULL) OR "
            "(scope = 'org_unit' AND org_unit_id IS NOT NULL AND user_id IS NULL) OR "
            "(scope = 'user' AND user_id IS NOT NULL AND org_unit_id IS NULL)",
            name="ck_blocked_periods_scope_consistency",
        ),
        UniqueConstraint("external_source", "external_ref", name="uq_blocked_periods_external_ref"),
    )

    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(String, nullable=False)
    org_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_units.id"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Заполнены только для периодов, созданных автосинхронизацией (например,
    # учебные планы из 1С) — идентифицируют исходную запись, чтобы повторный
    # синк обновлял/деактивировал те же строки, а не плодил дубли. NULL для
    # периодов, заведённых вручную через админку.
    external_source: Mapped[str | None] = mapped_column(String, nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
