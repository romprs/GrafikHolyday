"""reshape external_source_connection params to match real org-directory contract

Реальный контракт источника оргструктуры (GetDepartments(), Basic auth)
пришёл после того, как настройка уже была засеяна миграцией
3aa8180f408f со старой формой (base_url/api_key). Переносим на новую форму
(departments_url/auth_login/auth_password/verify_tls) — только если строка
всё ещё содержит старый ключ api_key (то есть её не трогали вручную под
реальные боевые значения, что для source, который был enabled=false и не
имел рабочего клиента, практически гарантировано).

Revision ID: 25df554f3aac
Revises: 3ee5b1f12ed4
Create Date: 2026-08-12 00:00:00.000000

"""
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '25df554f3aac'
down_revision = '3ee5b1f12ed4'
branch_labels = None
depends_on = None


NEW_PARAMS = {
    'departments_url': '',
    'auth_login': '',
    'auth_password': '',
    'verify_tls': False,
    'poll_interval_minutes': 60,
}


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE restriction_settings SET params = CAST(:params AS jsonb), "
            "description = 'Подключение к внешней системе-источнику оргструктуры (отделы)' "
            "WHERE key = 'external_source_connection' AND params ? 'api_key'"
        ),
        {"params": json.dumps(NEW_PARAMS)},
    )


def downgrade() -> None:
    # Данные, не схема — откатывать нечего.
    pass
