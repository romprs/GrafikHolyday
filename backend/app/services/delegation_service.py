import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationFailedError
from app.models.leave_delegation import LeaveDelegation
from app.models.user import User
from app.services import org_unit_service, permissions


def _check_can_grant(db: Session, actor: User, target_id: uuid.UUID) -> None:
    role = permissions.resolve_role(db, actor)
    if role == permissions.HR_ADMIN:
        return
    if role != permissions.MANAGER:
        raise ForbiddenError("Недостаточно прав для делегирования")

    target = db.get(User, target_id)
    visible = org_unit_service.visible_unit_ids(db, actor) or []
    if target is None or target.org_unit_id not in visible:
        raise ForbiddenError("Делегировать можно только за сотрудника из своей зоны ответственности")


def grant(
    db: Session, actor: User, delegate_user_id: uuid.UUID, target_user_id: uuid.UUID
) -> LeaveDelegation:
    if delegate_user_id == target_user_id:
        raise ValidationFailedError("Делегат и сотрудник не могут совпадать")
    if db.get(User, delegate_user_id) is None or db.get(User, target_user_id) is None:
        raise NotFoundError("Пользователь не найден")

    _check_can_grant(db, actor, target_user_id)

    existing = db.scalar(
        select(LeaveDelegation).where(
            LeaveDelegation.delegate_user_id == delegate_user_id,
            LeaveDelegation.target_user_id == target_user_id,
        )
    )
    if existing is not None:
        if not existing.is_active:
            existing.is_active = True
            existing.revoked_at = None
            existing.revoked_by = None
            db.commit()
            db.refresh(existing)
        return existing

    delegation = LeaveDelegation(
        delegate_user_id=delegate_user_id, target_user_id=target_user_id, created_by=actor.id
    )
    db.add(delegation)
    db.commit()
    db.refresh(delegation)
    return delegation


def revoke(db: Session, actor: User, delegation_id: uuid.UUID) -> None:
    delegation = db.get(LeaveDelegation, delegation_id)
    if delegation is None:
        raise NotFoundError("Делегирование не найдено")

    role = permissions.resolve_role(db, actor)
    if role != permissions.HR_ADMIN:
        _check_can_grant(db, actor, delegation.target_user_id)

    if delegation.is_active:
        delegation.is_active = False
        delegation.revoked_at = datetime.now(timezone.utc)
        delegation.revoked_by = actor.id
        db.commit()


def list_all(db: Session) -> list[LeaveDelegation]:
    return list(
        db.scalars(select(LeaveDelegation).order_by(LeaveDelegation.created_at.desc())).all()
    )


def list_visible(db: Session, actor: User) -> list[LeaveDelegation]:
    """Для не-HR — только делегирования, которые сам выдал или которые
    касаются сотрудников из его зоны видимости (чтобы руководитель видел
    делегирования по своим подчинённым, даже выданные HR)."""
    role = permissions.resolve_role(db, actor)
    if role == permissions.HR_ADMIN:
        return list_all(db)

    visible_units = org_unit_service.visible_unit_ids(db, actor) or []
    conditions = [LeaveDelegation.created_by == actor.id]
    if visible_units:
        conditions.append(User.org_unit_id.in_(visible_units))
    return list(
        db.scalars(
            select(LeaveDelegation)
            .join(User, User.id == LeaveDelegation.target_user_id)
            .where(or_(*conditions))
            .order_by(LeaveDelegation.created_at.desc())
        ).all()
    )


def can_act_for(db: Session, actor: User, target_user_id: uuid.UUID) -> bool:
    if actor.id == target_user_id:
        return True
    if permissions.resolve_role(db, actor) == permissions.HR_ADMIN:
        return True
    return (
        db.scalar(
            select(LeaveDelegation.id).where(
                LeaveDelegation.delegate_user_id == actor.id,
                LeaveDelegation.target_user_id == target_user_id,
                LeaveDelegation.is_active,
            )
        )
        is not None
    )


def resolve_subject(db: Session, actor: User, on_behalf_of: uuid.UUID | None) -> User:
    """Кто фактически действует (actor) vs чья это заявка/данные (subject) —
    общая точка входа для всех ручек, поддерживающих действие от имени
    другого сотрудника (заявки, баланс, недоступные периоды)."""
    if on_behalf_of is None or on_behalf_of == actor.id:
        return actor
    if not can_act_for(db, actor, on_behalf_of):
        raise ForbiddenError("Нет права действовать от имени этого сотрудника")
    subject = db.get(User, on_behalf_of)
    if subject is None:
        raise NotFoundError("Сотрудник не найден")
    return subject


def list_targets_for_delegate(db: Session, delegate: User) -> list[User]:
    """Сотрудники, за которых delegate может подавать/вести заявки —
    список для переключателя "от чьего имени" в UI."""
    return list(
        db.scalars(
            select(User)
            .join(LeaveDelegation, LeaveDelegation.target_user_id == User.id)
            .where(LeaveDelegation.delegate_user_id == delegate.id, LeaveDelegation.is_active)
            .order_by(User.full_name)
        ).all()
    )
