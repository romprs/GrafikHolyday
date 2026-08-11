import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from app.models.leave_request import (
    APPROVED,
    CANCELLED,
    PENDING_APPROVAL,
    REJECTED,
    STATUSES,
    LeaveRequest,
)
from app.models.user import User
from app.services import audit_service, org_unit_service


def _is_manager_of(db: Session, reviewer: User, target: User) -> bool:
    """Руководитель видит и согласовывает не только свой прямой отдел, но и
    всё, что ниже по управлению (каскад) — поэтому вышестоящий руководитель
    может согласовать заявку сотрудника из любого нижестоящего отдела, а не
    только те, что в его собственном org_unit."""
    if target.org_unit_id is None:
        return False
    return target.org_unit_id in set(org_unit_service.visible_unit_ids(db, reviewer) or [])


def _get_requests_for_submission(
    db: Session, reviewer: User, request_id: uuid.UUID, expected_status: str, conflict_message: str
) -> list[LeaveRequest]:
    """Все периоды одной заявки (submission_id), а не только запрошенный —
    заявка согласуется/отклоняется/отменяется целиком, одной транзакцией.
    У заявок, созданных до появления группировки, submission_id пуст — тогда
    группа состоит из одного периода."""
    request = db.get(LeaveRequest, request_id)
    if request is None:
        raise NotFoundError("Заявка не найдена")

    target = db.get(User, request.user_id)
    if target is None or not _is_manager_of(db, reviewer, target):
        raise ForbiddenError("Вы не являетесь руководителем отдела этого сотрудника")

    if request.status != expected_status:
        raise ConflictError(conflict_message, {"current_status": request.status})

    if request.submission_id is None:
        return [request]

    return list(
        db.scalars(
            select(LeaveRequest).where(
                LeaveRequest.submission_id == request.submission_id,
                LeaveRequest.status == expected_status,
            )
        ).all()
    )


def list_pending_for_manager(db: Session, manager: User) -> list[LeaveRequest]:
    managed_unit_ids = org_unit_service.visible_unit_ids(db, manager) or []
    if not managed_unit_ids:
        return []
    return list(
        db.scalars(
            select(LeaveRequest)
            .join(User, User.id == LeaveRequest.user_id)
            .where(
                User.org_unit_id.in_(managed_unit_ids),
                LeaveRequest.status == PENDING_APPROVAL,
            )
            .order_by(LeaveRequest.submitted_at)
        ).all()
    )


def approve(
    db: Session, reviewer: User, request_id: uuid.UUID, review_comment: str | None
) -> list[LeaveRequest]:
    requests = _get_requests_for_submission(
        db, reviewer, request_id, PENDING_APPROVAL, "Заявка уже обработана и недоступна для согласования"
    )
    now = datetime.now(timezone.utc)
    for request in requests:
        request.status = APPROVED
        request.reviewer_id = reviewer.id
        request.review_comment = review_comment
        request.reviewed_at = now
    db.commit()
    for request in requests:
        db.refresh(request)
    return requests


def reject(
    db: Session, reviewer: User, request_id: uuid.UUID, review_comment: str | None
) -> list[LeaveRequest]:
    requests = _get_requests_for_submission(
        db, reviewer, request_id, PENDING_APPROVAL, "Заявка уже обработана и недоступна для согласования"
    )
    now = datetime.now(timezone.utc)
    for request in requests:
        request.status = REJECTED
        request.reviewer_id = reviewer.id
        request.review_comment = review_comment
        request.reviewed_at = now
    db.commit()
    for request in requests:
        db.refresh(request)
    return requests


def list_approved_for_manager(db: Session, manager: User) -> list[LeaveRequest]:
    """Согласованные заявки сотрудников руководителя — чтобы он мог отменить
    уже согласованный период (единственный, кому это доступно, кроме
    сотрудника, который больше не может отменить сам себя после согласования
    — см. leave_request_service.cancel)."""
    managed_unit_ids = org_unit_service.visible_unit_ids(db, manager) or []
    if not managed_unit_ids:
        return []
    return list(
        db.scalars(
            select(LeaveRequest)
            .join(User, User.id == LeaveRequest.user_id)
            .where(
                User.org_unit_id.in_(managed_unit_ids),
                LeaveRequest.status == APPROVED,
            )
            .order_by(LeaveRequest.date_from)
        ).all()
    )


def manager_cancel_approved(
    db: Session, manager: User, request_id: uuid.UUID, review_comment: str | None
) -> list[LeaveRequest]:
    """Отмена уже согласованной заявки целиком (все её периоды) руководителем
    прямого отдела сотрудника — единственный способ отменить согласованную
    заявку помимо HR admin-override (см. admin_override)."""
    requests = _get_requests_for_submission(
        db, manager, request_id, APPROVED, "Отменить можно только уже согласованную заявку"
    )
    now = datetime.now(timezone.utc)
    for request in requests:
        request.status = CANCELLED
        request.reviewer_id = manager.id
        request.review_comment = review_comment
        request.reviewed_at = now
        request.cancelled_at = now
        request.cancelled_by = manager.id
    db.commit()
    for request in requests:
        db.refresh(request)
    return requests


def admin_override(
    db: Session,
    actor: User,
    request_id: uuid.UUID,
    reason: str,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
) -> LeaveRequest:
    """Единственный способ поправить уже согласованную/отклонённую заявку —
    только HR/админ (проверяется на уровне роутера), обязательна причина,
    каждая правка пишется в audit_log с полным до/после."""
    if not reason or not reason.strip():
        raise ValidationFailedError("Необходимо указать причину правки")

    request = db.get(LeaveRequest, request_id)
    if request is None:
        raise NotFoundError("Заявка не найдена")

    if status is not None and status not in STATUSES:
        raise ValidationFailedError("Недопустимый статус", {"status": status})

    before_state = {
        "date_from": str(request.date_from),
        "date_to": str(request.date_to),
        "status": request.status,
    }

    new_date_from = date_from if date_from is not None else request.date_from
    new_date_to = date_to if date_to is not None else request.date_to
    if new_date_to < new_date_from:
        raise ValidationFailedError("Дата окончания не может быть раньше даты начала")

    request.date_from = new_date_from
    request.date_to = new_date_to
    if status is not None:
        request.status = status

    after_state = {
        "date_from": str(request.date_from),
        "date_to": str(request.date_to),
        "status": request.status,
    }

    audit_service.log(
        db,
        "leave_request",
        request.id,
        "admin_override_edit",
        actor,
        reason,
        before_state,
        after_state,
    )
    db.commit()
    db.refresh(request)
    return request


def list_all(db: Session) -> list[LeaveRequest]:
    return list(db.scalars(select(LeaveRequest).order_by(LeaveRequest.submitted_at.desc())).all())
