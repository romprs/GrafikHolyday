"""leave_delegations: add org_unit scope (delegate for a whole department)

Revision ID: 395cc7fc327c
Revises: 25df554f3aac
Create Date: 2026-08-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '395cc7fc327c'
down_revision = '25df554f3aac'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'leave_delegations', sa.Column('scope', sa.String(), nullable=False, server_default='user')
    )
    op.alter_column('leave_delegations', 'scope', server_default=None)

    op.add_column('leave_delegations', sa.Column('target_org_unit_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_leave_delegations_target_org_unit_id',
        'leave_delegations', 'org_units', ['target_org_unit_id'], ['id'],
    )

    op.alter_column('leave_delegations', 'target_user_id', nullable=True)

    op.drop_constraint('ck_leave_delegations_distinct', 'leave_delegations', type_='check')
    op.create_check_constraint(
        'ck_leave_delegations_scope', 'leave_delegations', "scope IN ('user', 'org_unit')"
    )
    op.create_check_constraint(
        'ck_leave_delegations_scope_consistency',
        'leave_delegations',
        "(scope = 'user' AND target_user_id IS NOT NULL AND target_org_unit_id IS NULL) OR "
        "(scope = 'org_unit' AND target_org_unit_id IS NOT NULL AND target_user_id IS NULL)",
    )
    op.create_check_constraint(
        'ck_leave_delegations_distinct',
        'leave_delegations',
        'target_user_id IS NULL OR delegate_user_id != target_user_id',
    )


def downgrade() -> None:
    op.drop_constraint('ck_leave_delegations_distinct', 'leave_delegations', type_='check')
    op.drop_constraint('ck_leave_delegations_scope_consistency', 'leave_delegations', type_='check')
    op.drop_constraint('ck_leave_delegations_scope', 'leave_delegations', type_='check')
    op.create_check_constraint(
        'ck_leave_delegations_distinct', 'leave_delegations', 'delegate_user_id != target_user_id'
    )
    op.alter_column('leave_delegations', 'target_user_id', nullable=False)
    op.drop_constraint('fk_leave_delegations_target_org_unit_id', 'leave_delegations', type_='foreignkey')
    op.drop_column('leave_delegations', 'target_org_unit_id')
    op.drop_column('leave_delegations', 'scope')
