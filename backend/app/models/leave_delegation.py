import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class LeaveDelegation(UUIDPKMixin, Base):
    """Право подавать/вести заявки на отпуск от имени другого сотрудника —
    для тех, кто сам не пользуется системой (см. leave_request_service —
    любое действие с заявкой требует either target_user_id == actor, either
    активной делегации actor→target). Выдаётся HR (любая пара) или
    руководителем — но тогда только для сотрудника из своей (в т.ч.
    каскадной) видимости; делегатом при этом может быть кто угодно,
    в том числе из другого подразделения."""

    __tablename__ = "leave_delegations"
    __table_args__ = (
        CheckConstraint("delegate_user_id != target_user_id", name="ck_leave_delegations_distinct"),
    )

    delegate_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    target_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
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
