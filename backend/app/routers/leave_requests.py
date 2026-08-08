import uuid

from fastapi import APIRouter

from app.dependencies import CurrentUser, DbSession
from app.schemas.leave_request import LeaveRequestCreate, LeaveRequestOut, LeaveRequestReview
from app.services import approval_service, leave_request_service

router = APIRouter(prefix="/leave-requests", tags=["leave-requests"])


@router.post("", response_model=LeaveRequestOut)
def create_leave_request(
    body: LeaveRequestCreate, db: DbSession, user: CurrentUser
) -> LeaveRequestOut:
    request = leave_request_service.create_and_submit(
        db, user, body.date_from, body.date_to, body.comment
    )
    return request


@router.get("/mine", response_model=list[LeaveRequestOut])
def list_my_leave_requests(db: DbSession, user: CurrentUser) -> list[LeaveRequestOut]:
    return leave_request_service.list_own(db, user)


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
