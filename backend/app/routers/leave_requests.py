import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import CurrentUser, DbSession, require_role
from app.models.user import User
from app.schemas.leave_request import (
    LeaveRequestAdminOverride,
    LeaveRequestBulkCreate,
    LeaveRequestCreate,
    LeaveRequestOut,
    LeaveRequestReview,
)
from app.services import approval_service, leave_request_service, permissions

router = APIRouter(prefix="/leave-requests", tags=["leave-requests"])

HrAdmin = Annotated[User, Depends(require_role(permissions.HR_ADMIN))]


@router.post("", response_model=LeaveRequestOut)
def create_leave_request(
    body: LeaveRequestCreate, db: DbSession, user: CurrentUser
) -> LeaveRequestOut:
    request = leave_request_service.create_and_submit(
        db, user, body.date_from, body.date_to, body.comment
    )
    return request


@router.post("/bulk", response_model=list[LeaveRequestOut])
def create_leave_requests_bulk(
    body: LeaveRequestBulkCreate, db: DbSession, user: CurrentUser
) -> list[LeaveRequestOut]:
    periods = [(p.date_from, p.date_to, p.comment) for p in body.periods]
    return leave_request_service.create_and_submit_bulk(db, user, periods)


@router.get("/mine", response_model=list[LeaveRequestOut])
def list_my_leave_requests(db: DbSession, user: CurrentUser) -> list[LeaveRequestOut]:
    return leave_request_service.list_own(db, user)


@router.get("/all", response_model=list[LeaveRequestOut])
def list_all_leave_requests(db: DbSession, _: HrAdmin) -> list[LeaveRequestOut]:
    return approval_service.list_all(db)


@router.post("/{request_id}/cancel", response_model=LeaveRequestOut)
def cancel_leave_request(
    request_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> LeaveRequestOut:
    return leave_request_service.cancel(db, user, request_id)


@router.get("/team/pending", response_model=list[LeaveRequestOut])
def list_pending_for_my_team(db: DbSession, user: CurrentUser) -> list[LeaveRequestOut]:
    return approval_service.list_pending_for_manager(db, user)


@router.post("/{request_id}/approve", response_model=LeaveRequestOut)
def approve_leave_request(
    request_id: uuid.UUID, body: LeaveRequestReview, db: DbSession, user: CurrentUser
) -> LeaveRequestOut:
    return approval_service.approve(db, user, request_id, body.comment)


@router.post("/{request_id}/reject", response_model=LeaveRequestOut)
def reject_leave_request(
    request_id: uuid.UUID, body: LeaveRequestReview, db: DbSession, user: CurrentUser
) -> LeaveRequestOut:
    return approval_service.reject(db, user, request_id, body.comment)


@router.patch("/{request_id}/admin-override", response_model=LeaveRequestOut)
def admin_override_leave_request(
    request_id: uuid.UUID, body: LeaveRequestAdminOverride, db: DbSession, user: HrAdmin
) -> LeaveRequestOut:
    return approval_service.admin_override(
        db,
        user,
        request_id,
        body.reason,
        date_from=body.date_from,
        date_to=body.date_to,
        status=body.status,
    )
