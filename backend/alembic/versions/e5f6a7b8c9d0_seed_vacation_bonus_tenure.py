"""seed vacation_bonus_tenure_restriction setting

Новое ограничение на выплату ЕСВ по стажу (см. User.hire_date,
app/services/validation/vacation_bonus_tenure_rule.py). Выключено по
умолчанию (enabled=False) — включать осознанно, после того как HR
убедится, что дата приёма реально приходит из 1С по каждому сотруднику
(иначе включение до появления данных ничего не заблокирует, но и не
должно: сотрудников без hire_date правило пропускает).

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-18 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert


# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


restriction_settings = sa.table(
    'restriction_settings',
    sa.column('key', sa.String),
    sa.column('enabled', sa.Boolean),
    sa.column('params', sa.JSON),
    sa.column('description', sa.String),
)


def upgrade() -> None:
    stmt = pg_insert(restriction_settings).values(
        key='vacation_bonus_tenure_restriction',
        enabled=False,
        params={'months': 10},
        description='Ограничение на выплату ЕСВ по стажу (для проработавших менее года)',
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=['key'])
    op.execute(stmt)


def downgrade() -> None:
    # Данные, не схема — откатывать нечего.
    pass
