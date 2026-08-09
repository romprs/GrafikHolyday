import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationFailedError
from app.models.leave_request import APPROVED, CANCELLED, PENDING_APPROVAL, LeaveRequest
from app.models.leave_type import LeaveType
from app.models.user import User
from app.services import leave_balance_service
from app.services.validation import engine as validation_engine
from app.services.validation.types import Violation


def _get_vacation_leave_type(db: Session) -> LeaveType:
    leave_type = db.scalar(select(LeaveType).where(LeaveType.code == "vacation"))
    if leave_type is None:
        raise NotFoundError("Тип отсутствия 'vacation' не настроен")
    return leave_type


def create_and_submit(
    db: Session, user: User, date_from: date, date_to: date, comment: str | None
) -> LeaveRequest:
    violations = validation_engine.validate_leave_request(db, user, date_from, date_to)
    if violations:
        first = violations[0]
        raise ValidationFailedError(
            first.message_ru,
            {"violations": [v.__dict__ for v in violations]},
        )

    leave_type = _get_vacation_leave_type(db)
    now = datetime.now(timezone.utc)
    request = LeaveRequest(
        user_id=user.id,
        leave_type_id=leave_type.id,
        date_from=date_from,
        date_to=date_to,
        comment=comment,
        status=PENDING_APPROVAL,
        submitted_at=now,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def create_and_submit_bulk(
    db: Session, user: User, periods: list[tuple[date, date, str | None]]
) -> list[LeaveRequest]:
    """Несколько периодов одной пачкой — атомарно (либо все, либо ни одного).

    own_overlap_rule в движке проверяет только против уже сохранённых заявок
    (эти периоды ещё не в БД), поэтому пересечения периодов друг с другом
    внутри пачки и суммарный остаток по годам проверяются здесь отдельно.
    """
    if not periods:
        raise ValidationFailedError("Не указано ни одного периода")

    sorted_periods = sorted(periods, key=lambda p: p[0])
    for prev, curr in zip(sorted_periods, sorted_periods[1:]):
        if curr[0] <= prev[1]:
            raise ValidationFailedError(
                "Периоды в заявке пересекаются друг с другом",
                {
                    "period_a": {"date_from": str(prev[0]), "date_to": str(prev[1])},
                    "period_b": {"date_from": str(curr[0]), "date_to": str(curr[1])},
                },
            )

    all_violations: list[Violation] = []
    for date_from, date_to, _ in periods:
        all_violations.extend(validation_engine.validate_leave_request(db, user, date_from, date_to))

    if not user.has_benefits:
        days_by_year: dict[int, int] = {}
        for date_from, date_to, _ in periods:
            days_by_year[date_from.year] = (
                days_by_year.get(date_from.year, 0) + (date_to - date_from).days + 1
            )
        for year, total_days in days_by_year.items():
            remaining = leave_balance_service.get_remaining_for_new_request(db, user, year)
            if total_days > remaining:
                all_violations.append(
                    Violation(
                        code="LEAVE_BALANCE_EXCEEDED",
                        message_ru=f"Суммарно запрошено {total_days} дн. за {year} год, "
                        f"доступно {remaining} дн.",
                        params={"year": year, "requested_days": total_days, "remaining_days": remaining},
                    )
                )

    if all_violations:
        first = all_violations[0]
        raise ValidationFailedError(
            first.message_ru, {"violations": [v.__dict__ for v in all_violations]}
        )

    leave_type = _get_vacation_leave_type(db)
    now = datetime.now(timezone.utc)
    created = []
    for date_from, date_to, comment in periods:
        request = LeaveRequest(
            user_id=user.id,
            leave_type_id=leave_type.id,
            date_from=date_from,
            date_to=date_to,
            comment=comment,
            status=PENDING_APPROVAL,
            submitted_at=now,
        )
        db.add(request)
        created.append(request)
    db.commit()
    for request in created:
        db.refresh(request)
    return created


def get_own(db: Session, user: User, request_id: uuid.UUID) -> LeaveRequest:
    request = db.get(LeaveRequest, request_id)
    if request is None or request.user_id != user.id:
        raise NotFoundError("Заявка не найдена")
    return request


def list_team_approved(
    db: Session, user: User, date_from: date, date_to: date
) -> list[LeaveRequest]:
    """Согласованные отпуска коллег по прямому отделу (для командного календаря)."""
    if user.org_unit_id is None:
        return []
    return list(
        db.scalars(
            select(LeaveRequest)
            .join(User, User.id == LeaveRequest.user_id)
            .where(
                User.org_unit_id == user.org_unit_id,
                LeaveRequest.status == APPROVED,
                LeaveRequest.date_from <= date_to,
                LeaveRequest.date_to >= date_from,
            )
            .order_by(LeaveRequest.date_from)
        ).all()
    )


def list_own(db: Session, user: User) -> list[LeaveRequest]:
    return list(
        db.scalars(
            select(LeaveRequest)
            .where(LeaveRequest.user_id == user.id)
            .order_by(LeaveRequest.date_from.desc())
        ).all()
    )


def cancel(db: Session, user: User, request_id: uuid.UUID) -> LeaveRequest:
    request = get_own(db, user, request_id)
    if request.status not in (PENDING_APPROVAL, "approved"):
        raise ForbiddenError(
            "Отменить можно только заявку в статусе 'на согласовании' или 'согласована'",
            {"current_status": request.status},
        )

    request.status = CANCELLED
    request.cancelled_at = datetime.now(timezone.utc)
    request.cancelled_by = user.id
    db.commit()
    db.refresh(request)
    return request
