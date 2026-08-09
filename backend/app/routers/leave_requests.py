import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.dependencies import CurrentUser, DbSession, require_role
from app.models.leave_request import LeaveRequest
from app.models.user import User
from app.schemas.leave_request import (
    LeaveRequestAdminOverride,
    LeaveRequestBonusUpdate,
    LeaveRequestCreate,
    LeaveRequestOut,
    LeaveRequestReview,
    LeaveRequestWithEmployeeOut,
)
from app.services import approval_service, leave_request_service, permissions, restriction_settings_service

router = APIRouter(prefix="/leave-requests", tags=["leave-requests"])

HrAdmin = Annotated[User, Depends(require_role(permissions.HR_ADMIN))]


def _resolved_year(db: DbSession, year: int | None) -> int:
    return year if year is not None else restriction_settings_service.get_planning_year(db)


def _with_employee_names(
    db: DbSession, requests: list[LeaveRequest]
) -> list[LeaveRequestWithEmployeeOut]:
    user_ids = {r.user_id for r in requests}
    names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(user_ids)))}
    return [
        LeaveRequestWithEmployeeOut(
            **LeaveRequestOut.model_validate(r).model_dump(),
            user_full_name=names.get(r.user_id, "—"),
        )
        for r in requests
    ]


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


@router.patch("/drafts/{request_id}", response_model=LeaveRequestOut)
def update_draft(
    request_id: uuid.UUID, body: LeaveRequestBonusUpdate, db: DbSession, user: CurrentUser
) -> LeaveRequestOut:
    return leave_request_service.update_draft_bonus(db, user, request_id, body.bonus_requested)


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


@router.get("/team/pending", response_model=list[LeaveRequestWithEmployeeOut])
def list_pending_for_my_team(db: DbSession, user: CurrentUser) -> list[LeaveRequestWithEmployeeOut]:
    return _with_employee_names(db, approval_service.list_pending_for_manager(db, user))


@router.get("/team/approved", response_model=list[LeaveRequestWithEmployeeOut])
def list_approved_for_my_team(db: DbSession, user: CurrentUser) -> list[LeaveRequestWithEmployeeOut]:
    return _with_employee_names(db, approval_service.list_approved_for_manager(db, user))


@router.post("/{request_id}/manager-cancel", response_model=LeaveRequestOut)
def manager_cancel_leave_request(
    request_id: uuid.UUID, body: LeaveRequestReview, db: DbSession, user: CurrentUser
) -> LeaveRequestOut:
    return approval_service.manager_cancel_approved(db, user, request_id, body.comment)


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
