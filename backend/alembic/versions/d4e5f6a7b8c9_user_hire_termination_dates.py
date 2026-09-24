"""add hire_date/termination_date to users

Нужны для ограничения на выплату ЕСВ по стажу (см.
app/services/validation/vacation_bonus_tenure_rule.py) — синкаются из того
же источника 1С, что и дни отпуска (app/integrations/vacation_days.py).
Оба поля nullable: пока источник не прислал дату приёма, ограничение по
стажу просто не применяется к этому сотруднику (не блокирует и не падает).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('hire_date', sa.Date(), nullable=True))
    op.add_column('users', sa.Column('termination_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'termination_date')
    op.drop_column('users', 'hire_date')
