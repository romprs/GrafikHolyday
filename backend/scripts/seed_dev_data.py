"""Заполняет БД тестовыми данными для локальной разработки (до готовности реальной
синхронизации из внешней системы, см. app/sync/fake_client.py в Phase 3).

Запуск: .venv/bin/python -m scripts.seed_dev_data
"""

from datetime import date

from sqlalchemy import select

from app.database import SessionLocal
from app.models.blocked_period import GLOBAL, BlockedPeriod
from app.models.leave_balance import LeaveBalance
from app.models.leave_type import LeaveType
from app.models.org_unit import OrgUnit
from app.models.restriction_settings import (
    AUTH_CONFIGURATION,
    BLOCKED_PERIOD_ENFORCEMENT,
    DEPARTMENT_LOAD_THRESHOLDS,
    EXTERNAL_SOURCE_CONNECTION,
    LEAVE_BALANCE_LIMIT,
    MIN_LEAVE_DURATION,
    OWN_OVERLAP_CHECK,
    PLANNING_YEAR,
    RestrictionSettings,
    STUDY_PERIODS_SOURCE,
    VACATION_BONUS,
    VACATION_DAYS_SOURCE,
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
            (
                LEAVE_BALANCE_LIMIT,
                True,
                {},
                "Запрет заявок сверх остатка баланса отпуска",
            ),
            (
                OWN_OVERLAP_CHECK,
                True,
                {},
                "Запрет пересекающихся заявок одного сотрудника",
            ),
            (
                PLANNING_YEAR,
                True,
                {"year": current_year},
                "Год, на который сейчас ведётся планирование отпусков",
            ),
            (
                VACATION_BONUS,
                True,
                {"min_days": 14},
                "Порог длительности отпуска для дополнительной выплаты",
            ),
            (
                EXTERNAL_SOURCE_CONNECTION,
                False,
                {
                    "departments_url": "",
                    "employees_url": "",
                    "auth_login": "",
                    "auth_password": "",
                    "verify_tls": False,
                    "poll_interval_minutes": 60,
                },
                "Подключение к внешней системе-источнику оргструктуры (отделы и сотрудники)",
            ),
            (
                AUTH_CONFIGURATION,
                False,
                {
                    "mode": "dev",
                    "oidc_issuer": "",
                    "oidc_client_id": "",
                    "oidc_client_secret": "",
                    "oidc_redirect_uri": "",
                },
                "Настройки авторизации (dev-режим или OIDC)",
            ),
            (
                STUDY_PERIODS_SOURCE,
                False,
                {
                    "mode": "file",
                    "base_url": "",
                    "auth_login": "",
                    "auth_password": "",
                    "verify_tls": False,
                },
                "Источник учебных планов (недоступные периоды сотрудников)",
            ),
            (
                VACATION_DAYS_SOURCE,
                False,
                {"base_url": "", "auth_login": "", "auth_password": "", "verify_tls": False},
                "Источник остатка дней отпуска и признака льготника",
            ),
        )
        for key, enabled, params, description in default_settings:
            if db.get(RestrictionSettings, key) is None:
                db.add(
                    RestrictionSettings(
                        key=key, enabled=enabled, params=params, description=description
                    )
                )

        if db.scalar(select(BlockedPeriod).where(BlockedPeriod.reason == "Учебные сборы")) is None:
            db.add(
                BlockedPeriod(
                    date_from=date(date.today().year, date.today().month, 20),
                    date_to=date(date.today().year, date.today().month, 27),
                    reason="Учебные сборы",
                    scope=GLOBAL,
                    created_by=hr.id,
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
