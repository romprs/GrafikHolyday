"""split vacation_bonus_tenure_restriction into two independent settings

Пользователь указал на UI (одна строка с двумя параметрами и одним общим
чекбоксом/кнопкой "Сохранить"), что это фактически два разных ограничения
(новички / стажисты — разная механика, разные группы) и должны включаться
раздельно. Переносим params старой строки (если она есть — например, HR
уже успел её сохранить) в две новые, затем удаляем старую.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert


# revision identifiers, used by Alembic.
revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
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
    conn = op.get_bind()
    old = conn.execute(
        sa.select(restriction_settings.c.enabled, restriction_settings.c.params).where(
            restriction_settings.c.key == 'vacation_bonus_tenure_restriction'
        )
    ).first()

    old_enabled = old.enabled if old is not None else False
    old_params = (old.params or {}) if old is not None else {}
    new_hire_months = old_params.get('new_hire_months', old_params.get('months', 10))
    veteran_shift_months = old_params.get('veteran_shift_months', 6)

    stmt = pg_insert(restriction_settings).values(
        [
            {
                'key': 'vacation_bonus_new_hire_restriction',
                'enabled': old_enabled,
                'params': {'months': new_hire_months},
                'description': 'Выплата ЕСВ по стажу — новичкам (стаж менее года)',
            },
            {
                'key': 'vacation_bonus_veteran_restriction',
                'enabled': old_enabled,
                'params': {'shift_months': veteran_shift_months},
                'description': 'Выплата ЕСВ по стажу — стажистам (стаж год и более)',
            },
        ]
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=['key'])
    op.execute(stmt)

    op.execute(
        restriction_settings.delete().where(
            restriction_settings.c.key == 'vacation_bonus_tenure_restriction'
        )
    )


def downgrade() -> None:
    # Данные, не схема — откатывать нечего.
    pass
