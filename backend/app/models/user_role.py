import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin

# Единственная локальная (не синковая) роль — hr_admin.
# employee/manager вычисляются: manager = существует org_unit с head_user_id == user.id.
LOCAL_ROLES = ("hr_admin",)
_roles_sql_list = ", ".join(f"'{role}'" for role in LOCAL_ROLES)


class UserRole(UUIDPKMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        CheckConstraint(f"role IN ({_roles_sql_list})", name="ck_user_roles_role"),
        UniqueConstraint("user_id", "role", name="uq_user_roles_user_role"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
