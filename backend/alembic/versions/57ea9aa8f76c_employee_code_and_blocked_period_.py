"""employee_code and blocked_period external refs

Revision ID: 57ea9aa8f76c
Revises: c16c9d1a2e9a
Create Date: 2026-08-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '57ea9aa8f76c'
down_revision = 'c16c9d1a2e9a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('employee_code', sa.String(), nullable=True))
    op.create_unique_constraint('uq_users_employee_code', 'users', ['employee_code'])

    op.add_column('blocked_periods', sa.Column('external_source', sa.String(), nullable=True))
    op.add_column('blocked_periods', sa.Column('external_ref', sa.String(), nullable=True))
    op.create_unique_constraint(
        'uq_blocked_periods_external_ref', 'blocked_periods', ['external_source', 'external_ref']
    )


def downgrade() -> None:
    op.drop_constraint('uq_blocked_periods_external_ref', 'blocked_periods', type_='unique')
    op.drop_column('blocked_periods', 'external_ref')
    op.drop_column('blocked_periods', 'external_source')

    op.drop_constraint('uq_users_employee_code', 'users', type_='unique')
    op.drop_column('users', 'employee_code')
