"""sync_runs kind discriminator

Revision ID: b0f7a36a12aa
Revises: 57ea9aa8f76c
Create Date: 2026-08-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b0f7a36a12aa'
down_revision = '57ea9aa8f76c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'sync_runs',
        sa.Column('kind', sa.String(), nullable=False, server_default='org_directory'),
    )
    op.create_check_constraint(
        'ck_sync_runs_kind', 'sync_runs', "kind IN ('org_directory', 'study_periods')"
    )
    op.alter_column('sync_runs', 'kind', server_default=None)


def downgrade() -> None:
    op.drop_constraint('ck_sync_runs_kind', 'sync_runs', type_='check')
    op.drop_column('sync_runs', 'kind')
