from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class LeaveType(UUIDPKMixin, Base):
    """Справочник типов отсутствия. MVP: одна запись 'vacation'.

    Таблица, а не enum — чтобы позже добавить больничный/отгул без миграции схемы.
    """

    __tablename__ = "leave_types"

    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name_ru: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
