"""seed default restriction settings (incl. study_periods_source)

Продовая БД разворачивается через install.sh/alembic upgrade без
scripts/seed_dev_data.py (тот только для локальной разработки) — поэтому
restriction_settings там могла остаться пустой/неполной: ни один ключ не
заводится миграциями, только тестовым сидом. INSERT ... ON CONFLICT DO
NOTHING по первичному ключу (key) — безопасно и для БД, где часть строк уже
есть (созданы вручную через админку), и для полностью пустой таблицы.

Revision ID: 3aa8180f408f
Revises: b0f7a36a12aa
Create Date: 2026-08-11 00:00:00.000000

"""
from datetime import date

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert


# revision identifiers, used by Alembic.
revision = '3aa8180f408f'
down_revision = 'b0f7a36a12aa'
branch_labels = None
depends_on = None


restriction_settings = sa.table(
    'restriction_settings',
    sa.column('key', sa.String),
    sa.column('enabled', sa.Boolean),
    sa.column('params', sa.JSON),
    sa.column('description', sa.String),
)


def _default_rows() -> list[dict]:
    current_year = date.today().year
    return [
        {
            'key': 'min_leave_duration',
            'enabled': True,
            'params': {'min_days': 7},
            'description': 'Минимальная длительность отпуска',
        },
        {
            'key': 'blocked_period_enforcement',
            'enabled': True,
            'params': {},
            'description': 'Запрет пересечения отпуска с недоступными периодами',
        },
        {
            'key': 'department_load_thresholds',
            'enabled': True,
            'params': {'yellow': 0.30, 'red': 0.50},
            'description': 'Пороги подсветки загруженности отдела',
        },
        {
            'key': 'leave_balance_limit',
            'enabled': True,
            'params': {},
            'description': 'Запрет заявок сверх остатка баланса отпуска',
        },
        {
            'key': 'own_overlap_check',
            'enabled': True,
            'params': {},
            'description': 'Запрет пересекающихся заявок одного сотрудника',
        },
        {
            'key': 'planning_year',
            'enabled': True,
            'params': {'year': current_year},
            'description': 'Год, на который сейчас ведётся планирование отпусков',
        },
        {
            'key': 'vacation_bonus',
            'enabled': True,
            'params': {'min_days': 14},
            'description': 'Порог длительности отпуска для дополнительной выплаты',
        },
        {
            'key': 'external_source_connection',
            'enabled': False,
            'params': {'base_url': '', 'api_key': '', 'poll_interval_minutes': 60},
            'description': 'Подключение к внешней системе-источнику оргструктуры',
        },
        {
            'key': 'auth_configuration',
            'enabled': False,
            'params': {
                'mode': 'dev',
                'oidc_issuer': '',
                'oidc_client_id': '',
                'oidc_client_secret': '',
                'oidc_redirect_uri': '',
            },
            'description': 'Настройки авторизации (dev-режим или OIDC)',
        },
        {
            'key': 'study_periods_source',
            'enabled': False,
            'params': {
                'mode': 'file',
                'base_url': '',
                'auth_login': '',
                'auth_password': '',
                'verify_tls': False,
            },
            'description': 'Источник учебных планов (недоступные периоды сотрудников)',
        },
    ]


def upgrade() -> None:
    stmt = pg_insert(restriction_settings).values(_default_rows())
    stmt = stmt.on_conflict_do_nothing(index_elements=['key'])
    op.execute(stmt)


def downgrade() -> None:
    # Данные, не схема — откатывать нечего (могли быть отредактированы админом).
    pass
