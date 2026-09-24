"""seed default 'vacation' leave type

Продовая БД разворачивается через install.sh/alembic upgrade без
scripts/seed_dev_data.py (тот только для локальной разработки) — точно та
же ситуация, что уже была с restriction_settings (см. 3aa8180f408f), только
для leave_types этот сид никогда не добавляли. Без строки 'vacation' любая
попытка подать заявку на отпуск падает с "Тип отсутствия 'vacation' не
настроен" (app/services/leave_request_service.py) — на боевой базе,
поднятой только через install.sh, это ломает подачу заявок вообще для всех.

INSERT ... ON CONFLICT DO NOTHING по уникальному code — безопасно и для БД,
где строка уже есть (заведена вручную/сидом), и для полностью пустой таблицы.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-07 00:00:00.000000

"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


leave_types = sa.table(
    'leave_types',
    sa.column('id', sa.Uuid),
    sa.column('code', sa.String),
    sa.column('name_ru', sa.String),
    sa.column('is_active', sa.Boolean),
)


def upgrade() -> None:
    stmt = pg_insert(leave_types).values(
        id=uuid.uuid4(),
        code='vacation',
        name_ru='Отпуск',
        is_active=True,
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=['code'])
    op.execute(stmt)


def downgrade() -> None:
    # Данные, не схема — откатывать нечего (могли быть поданы заявки,
    # ссылающиеся на эту строку через leave_type_id).
    pass
