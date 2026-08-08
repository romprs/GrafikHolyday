import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class OrgUnit(UUIDPKMixin, TimestampMixin, Base):
    """Подразделение (управление/отдел/...) — произвольная глубина через parent_id.

    Данные владеет процесс синхронизации с внешней системой; в приложении read-only.
    """

    __tablename__ = "org_units"

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_units.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    unit_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    # use_alter: разрывает цикл org_units <-> users (users.org_unit_id -> org_units.id)
    # при создании таблиц — FK добавляется отдельным ALTER TABLE после обеих CREATE TABLE.
    head_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, name="fk_org_units_head_user_id"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
