import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.leave_request import APPROVED, DRAFT, PENDING_APPROVAL, LeaveRequest
from app.models.restriction_settings import DEPARTMENT_LOAD_THRESHOLDS
from app.models.user import User
from app.services import org_unit_service, permissions, restriction_settings_service

GREEN = "green"
YELLOW = "yellow"
RED = "red"


def _band(fraction: float, yellow_threshold: float, red_threshold: float) -> str:
    if fraction > red_threshold:
        return RED
    if fraction > yellow_threshold:
        return YELLOW
    return GREEN


def get_org_load(db: Session, org_unit_id: uuid.UUID, date_from: date, date_to: date) -> dict:
    """Загруженность юнита по дням с roll-up по всем дочерним подразделениям.

    Расчёт делается в Python поверх одной выборки заявок за диапазон, а не
    Postgres-специфичным generate_series — так это остаётся портируемым (и
    тестируемым на SQLite) при разумных объёмах данных корпоративного
    масштаба; при заметной нагрузке это первое место для профилирования.
    Сотрудники с has_benefits=True исключены и из числителя, и из знаменателя.
    """
    descendant_ids = org_unit_service.descendant_ids(db, org_unit_id)

    users = list(
        db.scalars(
            select(User).where(
                User.org_unit_id.in_(descendant_ids), User.is_active, ~User.has_benefits
            )
        ).all()
    )
    user_ids = {u.id for u in users}
    headcount = len(user_ids)

    requests = (
        list(
            db.scalars(
                select(LeaveRequest).where(
                    LeaveRequest.user_id.in_(user_ids),
                    LeaveRequest.status == APPROVED,
                    LeaveRequest.date_from <= date_to,
                    LeaveRequest.date_to >= date_from,
                )
            ).all()
        )
        if user_ids
        else []
    )

    thresholds_setting = restriction_settings_service.get(db, DEPARTMENT_LOAD_THRESHOLDS)
    yellow_threshold = (
        thresholds_setting.params.get("yellow", 0.30) if thresholds_setting else 0.30
    )
    red_threshold = thresholds_setting.params.get("red", 0.50) if thresholds_setting else 0.50

    days = []
    current = date_from
    while current <= date_to:
        on_leave = sum(1 for r in requests if r.date_from <= current <= r.date_to)
        fraction = (on_leave / headcount) if headcount else 0.0
        days.append(
            {
                "date": current,
                "on_leave": on_leave,
                "headcount": headcount,
                "fraction": fraction,
                "band": _band(fraction, yellow_threshold, red_threshold),
            }
        )
        current += timedelta(days=1)

    return {"org_unit_id": org_unit_id, "headcount": headcount, "days": days}


def get_org_leave_detail(
    db: Session, org_unit_id: uuid.UUID, date_from: date, date_to: date
) -> dict:
    """Сотрудники юнита (с ролью) и их отпуска за период — сырые данные для
    интерактивной таблицы (фильтры по роли, поиск, выбор конкретных
    сотрудников, список отпускников по клику на день считаются на фронте
    поверх одной этой выборки, без повторных запросов к API).

    Учитываются draft/pending_approval/approved — не только согласованные:
    руководителю нужно видеть уже выбранные и поданные, но ещё не
    рассмотренные периоды, чтобы оценить пересечения до принятия решения.
    """
    descendant_ids = org_unit_service.descendant_ids(db, org_unit_id)

    users = list(
        db.scalars(
            select(User).where(User.org_unit_id.in_(descendant_ids), User.is_active)
        ).all()
    )
    user_ids = {u.id for u in users}

    requests = (
        list(
            db.scalars(
                select(LeaveRequest).where(
                    LeaveRequest.user_id.in_(user_ids),
                    LeaveRequest.status.in_((DRAFT, PENDING_APPROVAL, APPROVED)),
                    LeaveRequest.date_from <= date_to,
                    LeaveRequest.date_to >= date_from,
                )
            ).all()
        )
        if user_ids
        else []
    )

    employees = [
        {"id": u.id, "full_name": u.full_name, "role": permissions.resolve_role(db, u)}
        for u in users
    ]
    leaves = [
        {
            "user_id": r.user_id,
            "date_from": r.date_from,
            "date_to": r.date_to,
            "status": r.status,
        }
        for r in requests
    ]

    return {"org_unit_id": org_unit_id, "employees": employees, "leaves": leaves}
