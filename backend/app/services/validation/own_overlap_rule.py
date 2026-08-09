from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.leave_request import APPROVED, DRAFT, PENDING_APPROVAL, LeaveRequest
from app.models.restriction_settings import OWN_OVERLAP_CHECK, RestrictionSettings
from app.models.user import User
from app.services.validation.types import Violation

KEY = OWN_OVERLAP_CHECK
# Не про льготы — сотрудник физически не может быть в двух отпусках сразу,
# поэтому льготники это правило не обходят.
EXEMPTABLE = False


def check(
    db: Session,
    settings_row: RestrictionSettings,
    user: User,
    date_from: date,
    date_to: date,
) -> Violation | None:
    overlapping = db.scalars(
        select(LeaveRequest).where(
            LeaveRequest.user_id == user.id,
            LeaveRequest.status.in_((APPROVED, PENDING_APPROVAL, DRAFT)),
            LeaveRequest.date_from <= date_to,
            LeaveRequest.date_to >= date_from,
        )
    ).all()
    if overlapping:
        first = overlapping[0]
        return Violation(
            code="OWN_REQUEST_OVERLAP",
            message_ru=f"Период пересекается с уже поданной заявкой "
            f"({first.date_from} — {first.date_to}).",
            params={
                "conflicting_requests": [
                    {"date_from": str(r.date_from), "date_to": str(r.date_to), "status": r.status}
                    for r in overlapping
                ]
            },
        )
    return None
