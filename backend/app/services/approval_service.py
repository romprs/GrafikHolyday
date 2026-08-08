import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.leave_request import APPROVED, PENDING_APPROVAL, REJECTED, LeaveRequest
from app.models.org_unit import OrgUnit
from app.models.user import User


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
