"""Заполняет БД тестовыми данными для локальной разработки (до готовности реальной
синхронизации из внешней системы, см. app/sync/fake_client.py в Phase 3).

Запуск: .venv/bin/python -m scripts.seed_dev_data
"""

from datetime import date

from sqlalchemy import select

from app.database import SessionLocal
from app.models.leave_balance import LeaveBalance
from app.models.leave_type import LeaveType
from app.models.org_unit import OrgUnit
from app.models.restriction_settings import (
    BLOCKED_PERIOD_ENFORCEMENT,
    DEPARTMENT_LOAD_THRESHOLDS,
    MIN_LEAVE_DURATION,
    RestrictionSettings,
)
from app.models.user import User
from app.models.user_role import UserRole


def seed() -> None:
    db = SessionLocal()
    try:
        if db.scalar(select(LeaveType).where(LeaveType.code == "vacation")) is None:
            db.add(LeaveType(code="vacation", name_ru="Отпуск"))

        upravlenie = db.scalar(select(OrgUnit).where(OrgUnit.name == "Управление продаж"))
        if upravlenie is None:
            upravlenie = OrgUnit(name="Управление продаж", unit_kind="управление")
            db.add(upravlenie)
            db.flush()

        otdel = db.scalar(select(OrgUnit).where(OrgUnit.name == "Отдел клиентского сервиса"))
        if otdel is None:
            otdel = OrgUnit(
                name="Отдел клиентского сервиса",
                unit_kind="отдел",
                parent_id=upravlenie.id,
            )
            db.add(otdel)
            db.flush()

        def ensure_user(email: str, full_name: str, has_benefits: bool = False) -> User:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email,
                    full_name=full_name,
                    org_unit_id=otdel.id,
                    has_benefits=has_benefits,
                )
                db.add(user)
                db.flush()
            return user

        manager = ensure_user("manager@example.com", "Ирина Руководитель")
        employee = ensure_user("employee@example.com", "Пётр Сотрудников")
        employee_benefits = ensure_user(
            "benefits@example.com", "Анна Льготникова", has_benefits=True
        )
        hr = db.scalar(select(User).where(User.email == "hr@example.com"))
        if hr is None:
            hr = User(email="hr@example.com", full_name="HR Админова", org_unit_id=None)
            db.add(hr)
            db.flush()
        if db.scalar(
            select(UserRole).where(UserRole.user_id == hr.id, UserRole.role == "hr_admin")
        ) is None:
            db.add(UserRole(user_id=hr.id, role="hr_admin"))

        otdel.head_user_id = manager.id

        current_year = date.today().year
        for u in (manager, employee, employee_benefits):
            if db.scalar(
                select(LeaveBalance).where(
                    LeaveBalance.user_id == u.id, LeaveBalance.year == current_year
                )
            ) is None:
                db.add(LeaveBalance(user_id=u.id, year=current_year, accrued_days=28))

        default_settings = (
            (MIN_LEAVE_DURATION, True, {"min_days": 7}, "Минимальная длительность отпуска"),
            (
                BLOCKED_PERIOD_ENFORCEMENT,
                True,
                {},
                "Запрет пересечения отпуска с недоступными периодами",
            ),
            (
                DEPARTMENT_LOAD_THRESHOLDS,
                True,
                {"yellow": 0.30, "red": 0.50},
                "Пороги подсветки загруженности отдела",
            ),
        )
        for key, enabled, params, description in default_settings:
            if db.get(RestrictionSettings, key) is None:
                db.add(
                    RestrictionSettings(
                        key=key, enabled=enabled, params=params, description=description
                    )
                )

        db.commit()
        print("Тестовые данные загружены:")
        for u in (manager, employee, employee_benefits, hr):
            print(f"  {u.email}  id={u.id}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
