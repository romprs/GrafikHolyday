"""Полная очистка данных, заведённых синхронизацией оргструктуры и
сотрудников (источник org_directory_rest — GetDepartments()/GetEmployeers(),
см. app/integrations/org_directory.py), для повторного импорта с чистого
листа.

Обычно в этом нет необходимости: баг, из-за которого сотрудники теряли
привязку к подразделению при раздельной загрузке (например, только
сотрудники без подразделений, или наоборот), исправлен в sync_service.py
(_resolve_ref) — обычный повторный запуск синхронизации/импорта сам
поправит org_unit_id у уже существующих сотрудников, ничего удалять не
нужно. Этот скрипт — на случай, если вы предпочитаете начать с чистого
листа, а не полагаться на самоисправление при следующем синке.

Удаляет ТОЛЬКО то, что было заведено этой синхронизацией — подразделения
и сотрудников определяем по external_id_mappings (external_system =
'org_directory_rest'). Подразделения/сотрудники, заведённые HR вручную
(нет записи в external_id_mappings), не трогает. Вместе с ними удаляются
их заявки на отпуск, баланс, недоступные периоды, делегирования, роли и
записи журнала изменений — то есть это разрушительная операция, уместная
только пока по этим сотрудникам не накопилось реальных данных (тестовая/
переходная фаза внедрения).

Запуск (без --yes — только покажет, что будет удалено, ничего не тронет):
  .venv/bin/python -m scripts.reset_org_directory_sync
  .venv/bin/python -m scripts.reset_org_directory_sync --yes
"""

import argparse

from sqlalchemy import bindparam, text

from app.database import SessionLocal
from app.services.sync_service import ORG_UNIT, USER

EXTERNAL_SYSTEM = "org_directory_rest"


def run(execute: bool) -> None:
    db = SessionLocal()
    try:
        user_ids = [
            row[0]
            for row in db.execute(
                text(
                    "SELECT internal_id FROM external_id_mappings "
                    "WHERE entity_type = :entity_type AND external_system = :system"
                ),
                {"entity_type": USER, "system": EXTERNAL_SYSTEM},
            )
        ]
        org_unit_ids = [
            row[0]
            for row in db.execute(
                text(
                    "SELECT internal_id FROM external_id_mappings "
                    "WHERE entity_type = :entity_type AND external_system = :system"
                ),
                {"entity_type": ORG_UNIT, "system": EXTERNAL_SYSTEM},
            )
        ]

        print(f"Синхронизированных сотрудников:    {len(user_ids)}")
        print(f"Синхронизированных подразделений:  {len(org_unit_ids)}")

        if not user_ids and not org_unit_ids:
            print("Нечего удалять — синхронизация ещё не запускалась.")
            return

        if not execute:
            print(
                "\nЭто предпросмотр — ничего не удалено. "
                "Запустите с флагом --yes, чтобы выполнить очистку."
            )
            return

        u_ids = bindparam("user_ids", value=user_ids, expanding=True)
        o_ids = bindparam("org_unit_ids", value=org_unit_ids, expanding=True)

        # Порядок важен: сперва снимаем ссылки/удаляем зависимые записи,
        # потом сами org_units/users, потом маппинг внешних id.
        db.execute(
            text("UPDATE org_units SET head_user_id = NULL WHERE head_user_id IN :user_ids").bindparams(u_ids)
        )
        db.execute(
            text(
                "UPDATE users SET org_unit_id = NULL "
                "WHERE org_unit_id IN :org_unit_ids AND id NOT IN :user_ids"
            ).bindparams(o_ids, u_ids)
        )
        db.execute(
            text(
                "UPDATE restriction_settings SET updated_by = NULL WHERE updated_by IN :user_ids"
            ).bindparams(u_ids)
        )

        db.execute(
            text(
                "DELETE FROM sync_change_log WHERE sync_run_id IN "
                "(SELECT id FROM sync_runs WHERE kind = 'org_directory')"
            )
        )
        db.execute(text("DELETE FROM sync_runs WHERE kind = 'org_directory'"))

        db.execute(
            text(
                "DELETE FROM audit_log WHERE performed_by IN :user_ids "
                "OR entity_id IN :user_ids OR entity_id IN :org_unit_ids"
            ).bindparams(u_ids, o_ids)
        )
        db.execute(
            text(
                "DELETE FROM leave_delegations WHERE delegate_user_id IN :user_ids "
                "OR target_user_id IN :user_ids OR target_org_unit_id IN :org_unit_ids "
                "OR created_by IN :user_ids OR revoked_by IN :user_ids"
            ).bindparams(u_ids, o_ids)
        )
        db.execute(
            text(
                "DELETE FROM blocked_periods WHERE user_id IN :user_ids "
                "OR org_unit_id IN :org_unit_ids OR created_by IN :user_ids"
            ).bindparams(u_ids, o_ids)
        )
        db.execute(
            text(
                "DELETE FROM leave_requests WHERE user_id IN :user_ids "
                "OR reviewer_id IN :user_ids OR acted_by IN :user_ids OR cancelled_by IN :user_ids"
            ).bindparams(u_ids)
        )
        db.execute(
            text(
                "DELETE FROM leave_balances WHERE user_id IN :user_ids OR updated_by IN :user_ids"
            ).bindparams(u_ids)
        )
        db.execute(
            text(
                "DELETE FROM user_roles WHERE user_id IN :user_ids OR created_by IN :user_ids"
            ).bindparams(u_ids)
        )

        db.execute(text("DELETE FROM users WHERE id IN :user_ids").bindparams(u_ids))
        db.execute(text("DELETE FROM org_units WHERE id IN :org_unit_ids").bindparams(o_ids))
        db.execute(
            text(
                "DELETE FROM external_id_mappings WHERE external_system = :system "
                "AND entity_type IN ('user', 'org_unit')"
            ),
            {"system": EXTERNAL_SYSTEM},
        )

        db.commit()
        print("\nГотово — можно запускать синхронизацию/импорт заново.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes", action="store_true", help="Выполнить удаление (без флага — только предпросмотр)"
    )
    args = parser.parse_args()
    run(execute=args.yes)
