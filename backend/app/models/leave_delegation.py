import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin

USER = "user"
ORG_UNIT = "org_unit"
SCOPES = (USER, ORG_UNIT)
_scopes_sql_list = ", ".join(f"'{s}'" for s in SCOPES)


class LeaveDelegation(UUIDPKMixin, Base):
    """Право подавать/вести заявки на отпуск от имени другого сотрудника —
    для тех, кто сам не пользуется системой (см. leave_request_service —
    любое действие с заявкой требует либо target_user_id == actor, либо
    активной делегации actor→target, прямой или через подразделение).

    Два вида (по аналогии с BlockedPeriod.scope):
    - user: делегат ведёт заявки одного конкретного сотрудника;
    - org_unit: делегат ведёт заявки всех сотрудников подразделения и всех
      нижестоящих (тот же каскад, что и у видимости руководителя —
      см. org_unit_service.descendant_ids) — иначе на сколько-нибудь
      крупном отделе делегирование по одному человеку не масштабируется.

    Выдаётся HR (любая пара/любое подразделение) или руководителем — но
    тогда только для сотрудника/подразделения из своей (в т.ч. каскадной)
    видимости; делегатом при этом может быть кто угодно, в том числе из
    другого подразделения.
    """

    __tablename__ = "leave_delegations"
    __table_args__ = (
        CheckConstraint(f"scope IN ({_scopes_sql_list})", name="ck_leave_delegations_scope"),
        CheckConstraint(
            "(scope = 'user' AND target_user_id IS NOT NULL AND target_org_unit_id IS NULL) OR "
            "(scope = 'org_unit' AND target_org_unit_id IS NOT NULL AND target_user_id IS NULL)",
            name="ck_leave_delegations_scope_consistency",
        ),
        CheckConstraint(
            "target_user_id IS NULL OR delegate_user_id != target_user_id",
            name="ck_leave_delegations_distinct",
        ),
    )

    scope: Mapped[str] = mapped_column(String, nullable=False, default=USER)
    delegate_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    target_org_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_units.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
