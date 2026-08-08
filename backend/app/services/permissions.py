from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.org_unit import OrgUnit
from app.models.user import User
from app.models.user_role import UserRole

EMPLOYEE = "employee"
MANAGER = "manager"
HR_ADMIN = "hr_admin"


def resolve_role(db: Session, user: User) -> str:
    """Роль вычисляется, а не хранится — не может разойтись с синковыми данными.

    hr_admin — локальное назначение (user_roles); manager — вычисляется по факту
    того, что пользователь указан как head_user_id хотя бы одного org_unit.
    """
    is_hr_admin = db.scalar(
        select(exists().where(UserRole.user_id == user.id, UserRole.role == HR_ADMIN))
    )
    if is_hr_admin:
        return HR_ADMIN

    is_manager = db.scalar(
        select(exists().where(OrgUnit.head_user_id == user.id, OrgUnit.is_active))
    )
    if is_manager:
        return MANAGER

    return EMPLOYEE
