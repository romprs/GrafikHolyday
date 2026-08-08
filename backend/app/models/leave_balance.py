import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class LeaveBalance(UUIDPKMixin, Base):
    """Начисленные дни отпуска за год. used/remaining считаются на лету
    (сумма approved-заявок за год) в leave_balance_service, а не хранятся здесь —
    чтобы не рассинхронизироваться с leave_requests при отмене/согласовании.
    """

    __tablename__ = "leave_balances"
    __table_args__ = (UniqueConstraint("user_id", "year", name="uq_leave_balances_user_year"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    accrued_days: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    carried_over_days: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
