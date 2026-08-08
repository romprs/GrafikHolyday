import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin

ENTITY_TYPES = ("org_unit", "user")
_entity_types_sql_list = ", ".join(f"'{t}'" for t in ENTITY_TYPES)


class ExternalIdMapping(UUIDPKMixin, Base):
    """Единая таблица маппинга внешних ID → внутренние — не размазываем
    external_id по org_units/users, что позволяет добавить второй внешний
    источник или тип сущности без изменения их схемы."""

    __tablename__ = "external_id_mappings"
    __table_args__ = (
        CheckConstraint(f"entity_type IN ({_entity_types_sql_list})", name="ck_ext_map_entity_type"),
        UniqueConstraint(
            "entity_type", "external_system", "external_id", name="uq_ext_map_identity"
        ),
    )

    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    external_system: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    internal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
