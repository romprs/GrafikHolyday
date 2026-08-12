import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationFailedError
from app.models.org_unit import OrgUnit
from app.models.user import User
from app.models.user_role import LOCAL_ROLES, UserRole
from app.services import permissions


def list_users_with_roles(db: Session) -> list[tuple[User, str]]:
    users = list(db.scalars(select(User).order_by(User.full_name)).all())
    return [(u, permissions.resolve_role(db, u)) for u in users]


def _check_email_free(db: Session, email: str, exclude_id: uuid.UUID | None) -> None:
    query = select(User.id).where(User.email == email)
    if exclude_id is not None:
        query = query.where(User.id != exclude_id)
    if db.scalar(query) is not None:
        raise ValidationFailedError("Такой email уже используется другим сотрудником", {"email": email})


def create_user(
    db: Session,
    email: str,
    full_name: str,
    org_unit_id: uuid.UUID | None,
    has_benefits: bool,
    employee_code: str | None,
) -> User:
    """Ручное создание сотрудника HR — наравне с теми, что приходят из
    синхронизации: у синка нет своего внешнего маппинга на такого
    пользователя, так что он его не тронет."""
    email = email.strip()
    if not email:
        raise ValidationFailedError("Email обязателен")
    _check_email_free(db, email, exclude_id=None)

    if org_unit_id is not None and db.get(OrgUnit, org_unit_id) is None:
        raise NotFoundError("Подразделение не найдено")

    code = (employee_code or "").strip() or None
    if code:
        clash = db.scalar(select(User.id).where(User.employee_code == code))
        if clash is not None:
            raise ValidationFailedError(
                "Табельный номер уже используется другим сотрудником", {"employee_code": code}
            )

    user = User(
        email=email,
        full_name=full_name.strip(),
        org_unit_id=org_unit_id,
        has_benefits=has_benefits,
        employee_code=code,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    user_id: uuid.UUID,
    email: str,
    full_name: str,
    org_unit_id: uuid.UUID | None,
    has_benefits: bool,
    is_active: bool,
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("Пользователь не найден")

    email = email.strip()
    if not email:
        raise ValidationFailedError("Email обязателен")
    _check_email_free(db, email, exclude_id=user_id)

    if org_unit_id is not None and db.get(OrgUnit, org_unit_id) is None:
        raise NotFoundError("Подразделение не найдено")

    user.email = email
    user.full_name = full_name.strip()
    user.org_unit_id = org_unit_id
    user.has_benefits = has_benefits
    user.is_active = is_active
    if not is_active:
        # Деактивированный сотрудник больше не может войти (см.
        # dependencies.get_current_user) — но если он числился руководителем
        # подразделения, эту ссылку стоит явно снять, а не оставлять
        # "руководителя", который не может залогиниться.
        for unit in db.scalars(select(OrgUnit).where(OrgUnit.head_user_id == user_id)).all():
            unit.head_user_id = None
    db.commit()
    db.refresh(user)
    return user


def deactivate_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("Пользователь не найден")
    return update_user(
        db, user_id, user.email, user.full_name, user.org_unit_id, user.has_benefits, is_active=False
    )


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
