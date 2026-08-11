"""leave delegations + leave_requests.acted_by

Revision ID: 3ee5b1f12ed4
Revises: 3aa8180f408f
Create Date: 2026-08-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3ee5b1f12ed4'
down_revision = '3aa8180f408f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'leave_delegations',
        sa.Column('delegate_user_id', sa.UUID(), nullable=False),
        sa.Column('target_user_id', sa.UUID(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_by', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.CheckConstraint('delegate_user_id != target_user_id', name='ck_leave_delegations_distinct'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['delegate_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['revoked_by'], ['users.id']),
        sa.ForeignKeyConstraint(['target_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.add_column('leave_requests', sa.Column('acted_by', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_leave_requests_acted_by', 'leave_requests', 'users', ['acted_by'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_leave_requests_acted_by', 'leave_requests', type_='foreignkey')
    op.drop_column('leave_requests', 'acted_by')
    op.drop_table('leave_delegations')
