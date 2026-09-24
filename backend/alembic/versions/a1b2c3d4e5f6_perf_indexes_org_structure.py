"""perf indexes for org structure / org load lookups

Revision ID: a1b2c3d4e5f6
Revises: f206121b1d61
Create Date: 2026-09-01 00:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f206121b1d61'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # org_units.parent_id — рекурсивные CTE (ancestor_ids/descendant_ids,
    # org_unit_service) фильтруют по нему на каждом уровне дерева; без
    # индекса это seq scan по всей таблице подразделений на каждый уровень.
    op.create_index('ix_org_units_parent_id', 'org_units', ['parent_id'])
    # org_units.head_user_id — permissions.resolve_role() проверяет его на
    # КАЖДЫЙ запрос (не hr_admin) через exists(); также используется в
    # headed_unit_ids() и в bulk-резолвинге ролей (resolve_roles_bulk).
    op.create_index('ix_org_units_head_user_id', 'org_units', ['head_user_id'])
    # users.org_unit_id — org_load_service фильтрует сотрудников юнита
    # (`.in_(descendant_ids)`) на каждый показ дашборда загруженности.
    op.create_index('ix_users_org_unit_id', 'users', ['org_unit_id'])
    # leave_requests.user_id — org_load_service фильтрует заявки диапазона
    # по списку сотрудников юнита (`.in_(user_ids)`) на каждый показ того же
    # дашборда; таблица растёт со временем, актуальность индекса тоже.
    op.create_index('ix_leave_requests_user_id', 'leave_requests', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_leave_requests_user_id', table_name='leave_requests')
    op.drop_index('ix_users_org_unit_id', table_name='users')
    op.drop_index('ix_org_units_head_user_id', table_name='org_units')
    op.drop_index('ix_org_units_parent_id', table_name='org_units')
