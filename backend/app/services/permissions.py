from typing import Sequence

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

    Для ОДНОГО пользователя (текущий актор запроса) — 1-2 запроса, ожидаемо.
    Для списка пользователей использовать resolve_roles_bulk(), а не звать
    эту функцию в цикле — иначе N пользователей дают до 2N запросов (см.
    исправленный баг в user_admin_service.list_users_with_roles и
    org_load_service.get_org_leave_detail).
    """
    is_hr_admin = db.scalar(
        select(exists().where(UserRole.user_id == user.id, UserRole.role == HR_ADMIN))
    )
    if is_hr_admin:
        return HR_ADMIN

    if is_org_unit_head(db, user):
        return MANAGER

    return EMPLOYEE


def is_org_unit_head(db: Session, user: User) -> bool:
    """Независимо от role() (там hr_admin перекрывает manager) — реально ли
    этот пользователь возглавляет хоть одно активное подразделение. Нужно
    отдельно, чтобы HR-admin, совмещающий роль с руководством отделом, тоже
    видел пункт согласования по своим подчинённым (см. CurrentUserOut)."""
    return bool(
        db.scalar(select(exists().where(OrgUnit.head_user_id == user.id, OrgUnit.is_active)))
    )


def resolve_roles_bulk(db: Session, users: Sequence[User]) -> dict:
    """То же самое, что resolve_role(), но для многих пользователей сразу —
    2 запроса независимо от количества пользователей, а не 2 на каждого."""
    user_ids = [u.id for u in users]
    if not user_ids:
        return {}

    hr_admin_ids = set(
        db.scalars(
            select(UserRole.user_id).where(
                UserRole.user_id.in_(user_ids), UserRole.role == HR_ADMIN
            )
        )
    )
    manager_ids = set(
        db.scalars(
            select(OrgUnit.head_user_id).where(
                OrgUnit.head_user_id.in_(user_ids), OrgUnit.is_active
            )
        )
    )

    def role_of(user_id: object) -> str:
        if user_id in hr_admin_ids:
            return HR_ADMIN
        if user_id in manager_ids:
            return MANAGER
        return EMPLOYEE

    return {u.id: role_of(u.id) for u in users}
