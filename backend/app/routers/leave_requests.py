import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import CurrentUser, DbSession, require_role
from app.models.user import User
from app.schemas.leave_request import (
    LeaveRequestAdminOverride,
    LeaveRequestCreate,
    LeaveRequestOut,
    LeaveRequestReview,
)
from app.services import approval_service, leave_request_service, permissions, restriction_settings_service

router = APIRouter(prefix="/leave-requests", tags=["leave-requests"])

HrAdmin = Annotated[User, Depends(require_role(permissions.HR_ADMIN))]


def _resolved_year(db: DbSession, year: int | None) -> int:
    return year if year is not None else restriction_settings_service.get_planning_year(db)


@router.get("/drafts", response_model=list[LeaveRequestOut])
def list_drafts(db: DbSession, user: CurrentUser, year: int | None = None) -> list[LeaveRequestOut]:
    return leave_request_service.list_drafts(db, user, _resolved_year(db, year))


@router.post("/drafts", response_model=LeaveRequestOut)
def add_draft(body: LeaveRequestCreate, db: DbSession, user: CurrentUser) -> LeaveRequestOut:
    return leave_request_service.create_draft(
        db, user, body.date_from, body.date_to, body.comment, body.bonus_requested
    )


@router.delete("/drafts/{request_id}", status_code=204)
def remove_draft(request_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    leave_request_service.delete_draft(db, user, request_id)


@router.post("/submit", response_model=list[LeaveRequestOut])
def submit_drafts(db: DbSession, user: CurrentUser, year: int | None = None) -> list[LeaveRequestOut]:
    return leave_request_service.submit_drafts(db, user, _resolved_year(db, year))


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
