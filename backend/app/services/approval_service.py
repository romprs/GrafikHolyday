import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from app.models.leave_request import APPROVED, PENDING_APPROVAL, REJECTED, STATUSES, LeaveRequest
from app.models.org_unit import OrgUnit
from app.models.user import User
from app.services import audit_service


def _is_direct_manager_of(db: Session, reviewer: User, target: User) -> bool:
    """MVP: согласование только руководителем прямого отдела сотрудника —
    без каскадного доступа руководителей вышестоящих управлений."""
    if target.org_unit_id is None:
        return False
    return db.scalar(
        select(OrgUnit.id).where(
            OrgUnit.id == target.org_unit_id,
            OrgUnit.head_user_id == reviewer.id,
            OrgUnit.is_active,
        )
    ) is not None


def _get_pending_request_for_review(
    db: Session, reviewer: User, request_id: uuid.UUID
) -> LeaveRequest:
    request = db.get(LeaveRequest, request_id)
    if request is None:
        raise NotFoundError("Заявка не найдена")

    target = db.get(User, request.user_id)
    if target is None or not _is_direct_manager_of(db, reviewer, target):
        raise ForbiddenError("Вы не являетесь руководителем отдела этого сотрудника")

    if request.status != PENDING_APPROVAL:
        raise ConflictError(
            "Заявка уже обработана и недоступна для согласования",
            {"current_status": request.status},
        )
    return request


def list_pending_for_manager(db: Session, manager: User) -> list[LeaveRequest]:
    managed_unit_ids = db.scalars(
        select(OrgUnit.id).where(OrgUnit.head_user_id == manager.id, OrgUnit.is_active)
    ).all()
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
) -> LeaveRequest:
    request = _get_pending_request_for_review(db, reviewer, request_id)
    request.status = APPROVED
    request.reviewer_id = reviewer.id
    request.review_comment = review_comment
    request.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(request)
    return request


def reject(
    db: Session, reviewer: User, request_id: uuid.UUID, review_comment: str | None
) -> LeaveRequest:
    request = _get_pending_request_for_review(db, reviewer, request_id)
    request.status = REJECTED
    request.reviewer_id = reviewer.id
    request.review_comment = review_comment
    request.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(request)
    return request


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
