import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin

STATUSES = ("draft", "pending_approval", "approved", "rejected", "cancelled")
_statuses_sql_list = ", ".join(f"'{s}'" for s in STATUSES)

DRAFT = "draft"
PENDING_APPROVAL = "pending_approval"
APPROVED = "approved"
REJECTED = "rejected"
CANCELLED = "cancelled"


class LeaveRequest(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "leave_requests"
    __table_args__ = (
        CheckConstraint(f"status IN ({_statuses_sql_list})", name="ck_leave_requests_status"),
        CheckConstraint("date_to >= date_from", name="ck_leave_requests_date_order"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leave_types.id"), nullable=False
    )
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default=PENDING_APPROVAL)
    # Дополнительная выплата к отпуску — доступна при длительности периода
    # больше порога из restriction_settings[VACATION_BONUS] (см. validation).
    bonus_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Общий id для всех периодов, отправленных на согласование одним нажатием
    # submit_drafts — руководитель согласовывает/отклоняет всю пачку разом,
    # а не по одному периоду. NULL у черновиков и у заявок, созданных до
    # появления этого поля.
    submission_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Кто фактически создал/подал заявку, если не сам сотрудник (user_id) —
    # делегат или руководитель, действующий от его имени (см.
    # app/services/delegation_service.py). NULL — заявка от самого себя.
    acted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    @property
    def days(self) -> int:
        return (self.date_to - self.date_from).days + 1
