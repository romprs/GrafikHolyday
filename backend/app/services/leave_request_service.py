import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationFailedError
from app.models.leave_request import APPROVED, CANCELLED, PENDING_APPROVAL, LeaveRequest
from app.models.leave_type import LeaveType
from app.models.user import User
from app.services.validation import engine as validation_engine


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
