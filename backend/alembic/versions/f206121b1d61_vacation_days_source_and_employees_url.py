"""vacation_days_source setting + employees_url on external_source_connection + sync_runs.kind

Revision ID: f206121b1d61
Revises: 395cc7fc327c
Create Date: 2026-08-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f206121b1d61'
down_revision = '395cc7fc327c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('ck_sync_runs_kind', 'sync_runs', type_='check')
    op.create_check_constraint(
        'ck_sync_runs_kind', 'sync_runs', "kind IN ('org_directory', 'study_periods', 'vacation_days')"
    )

    conn = op.get_bind()
    # jsonb || — добавляет ключ, если его ещё нет, и не трогает остальные
    # (в т.ч. уже отредактированные вручную) значения строки.
    conn.execute(
        sa.text(
            "UPDATE restriction_settings SET params = params || '{\"employees_url\": \"\"}'::jsonb "
            "WHERE key = 'external_source_connection'"
        )
    )
    conn.execute(
        sa.text(
            "INSERT INTO restriction_settings (key, enabled, params, description) "
            "VALUES ('vacation_days_source', false, "
            "'{\"base_url\": \"\", \"auth_login\": \"\", \"auth_password\": \"\", \"verify_tls\": false}'::jsonb, "
            "'Источник остатка дней отпуска и признака льготника') "
            "ON CONFLICT (key) DO NOTHING"
        )
    )


def downgrade() -> None:
    op.drop_constraint('ck_sync_runs_kind', 'sync_runs', type_='check')
    op.create_check_constraint(
        'ck_sync_runs_kind', 'sync_runs', "kind IN ('org_directory', 'study_periods')"
    )
    # Данные — не откатываем ключи настроек, оставляем как есть.
