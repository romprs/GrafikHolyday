import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationFailedError
from app.models.user import User
from app.models.user_role import LOCAL_ROLES, UserRole
from app.services import permissions


def list_users_with_roles(db: Session) -> list[tuple[User, str]]:
    users = list(db.scalars(select(User).order_by(User.full_name)).all())
    return [(u, permissions.resolve_role(db, u)) for u in users]


def grant_role(db: Session, actor: User, user_id: uuid.UUID, role: str) -> None:
    if role not in LOCAL_ROLES:
        raise ValidationFailedError("Эту роль нельзя назначить вручную", {"role": role})
    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("Пользователь не найден")

    existing = db.scalar(
        select(UserRole).where(UserRole.user_id == target.id, UserRole.role == role)
    )
    if existing is None:
        db.add(UserRole(user_id=target.id, role=role, created_by=actor.id))
        db.commit()


def set_employee_code(db: Session, user_id: uuid.UUID, employee_code: str | None) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("Пользователь не найден")

    code = employee_code.strip() if employee_code else None
    code = code or None
    if code:
        clash = db.scalar(select(User).where(User.employee_code == code, User.id != target.id))
        if clash is not None:
            raise ValidationFailedError(
                "Табельный номер уже используется другим сотрудником", {"employee_code": code}
            )
    target.employee_code = code
    db.commit()
    db.refresh(target)
    return target


def revoke_role(db: Session, actor: User, user_id: uuid.UUID, role: str) -> None:
    if role not in LOCAL_ROLES:
        raise ValidationFailedError("Эту роль нельзя отозвать вручную", {"role": role})
    if user_id == actor.id:
        raise ForbiddenError("Нельзя отозвать эту роль у самого себя")

    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("Пользователь не найден")

    existing = db.scalar(
        select(UserRole).where(UserRole.user_id == target.id, UserRole.role == role)
    )
    if existing is not None:
        db.delete(existing)
        db.commit()
