"""Заполняет БД тестовыми данными для локальной разработки (до готовности реальной
синхронизации из внешней системы, см. app/sync/fake_client.py в Phase 3).

Запуск: .venv/bin/python -m scripts.seed_dev_data
"""

from sqlalchemy import select

from app.database import SessionLocal
from app.models.leave_type import LeaveType
from app.models.org_unit import OrgUnit
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

        db.commit()
        print("Тестовые данные загружены:")
        for u in (manager, employee, employee_benefits, hr):
            print(f"  {u.email}  id={u.id}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
