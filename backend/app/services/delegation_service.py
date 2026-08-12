import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationFailedError
from app.models.leave_delegation import ORG_UNIT, USER, LeaveDelegation
from app.models.org_unit import OrgUnit
from app.models.user import User
from app.services import org_unit_service, permissions


def _check_can_grant_for_user(db: Session, actor: User, target_user_id: uuid.UUID) -> None:
    role = permissions.resolve_role(db, actor)
    if role == permissions.HR_ADMIN:
        return
    if role != permissions.MANAGER:
        raise ForbiddenError("Недостаточно прав для делегирования")

    target = db.get(User, target_user_id)
    visible = org_unit_service.visible_unit_ids(db, actor) or []
    if target is None or target.org_unit_id not in visible:
        raise ForbiddenError("Делегировать можно только за сотрудника из своей зоны ответственности")


def _check_can_grant_for_unit(db: Session, actor: User, target_org_unit_id: uuid.UUID) -> None:
    role = permissions.resolve_role(db, actor)
    if role == permissions.HR_ADMIN:
        return
    if role != permissions.MANAGER:
        raise ForbiddenError("Недостаточно прав для делегирования")

    visible = org_unit_service.visible_unit_ids(db, actor) or []
    if target_org_unit_id not in visible:
        raise ForbiddenError(
            "Делегировать можно только за подразделение из своей зоны ответственности"
        )


def grant(
    db: Session,
    actor: User,
    delegate_user_id: uuid.UUID,
    target_user_id: uuid.UUID | None = None,
    target_org_unit_id: uuid.UUID | None = None,
) -> LeaveDelegation:
    """Ровно одно из target_user_id/target_org_unit_id — делегат ведёт
    заявки либо одного сотрудника, либо всех сотрудников подразделения (и
    всех нижестоящих, тот же каскад, что у видимости руководителя)."""
    if (target_user_id is None) == (target_org_unit_id is None):
        raise ValidationFailedError(
            "Нужно указать либо сотрудника, либо подразделение — ровно одно"
        )
    if db.get(User, delegate_user_id) is None:
        raise NotFoundError("Делегат не найден")

    if target_user_id is not None:
        if delegate_user_id == target_user_id:
            raise ValidationFailedError("Делегат и сотрудник не могут совпадать")
        if db.get(User, target_user_id) is None:
            raise NotFoundError("Сотрудник не найден")
        _check_can_grant_for_user(db, actor, target_user_id)
        scope = USER
        match_filter = LeaveDelegation.target_user_id == target_user_id
    else:
        if db.get(OrgUnit, target_org_unit_id) is None:
            raise NotFoundError("Подразделение не найдено")
        _check_can_grant_for_unit(db, actor, target_org_unit_id)
        scope = ORG_UNIT
        match_filter = LeaveDelegation.target_org_unit_id == target_org_unit_id

    existing = db.scalar(
        select(LeaveDelegation).where(
            LeaveDelegation.delegate_user_id == delegate_user_id,
            LeaveDelegation.scope == scope,
            match_filter,
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
        scope=scope,
        delegate_user_id=delegate_user_id,
        target_user_id=target_user_id,
        target_org_unit_id=target_org_unit_id,
        created_by=actor.id,
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
        if delegation.scope == USER:
            _check_can_grant_for_user(db, actor, delegation.target_user_id)
        else:
            _check_can_grant_for_unit(db, actor, delegation.target_org_unit_id)

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
    """Для не-HR — только делегирования, которые сам выдал, или которые
    касаются сотрудника/подразделения из его зоны видимости (чтобы
    руководитель видел делегирования по своим подчинённым, даже выданные
    HR или вышестоящим руководителем)."""
    role = permissions.resolve_role(db, actor)
    if role == permissions.HR_ADMIN:
        return list_all(db)

    visible_units = set(org_unit_service.visible_unit_ids(db, actor) or [])
    result = []
    for delegation in list_all(db):
        if delegation.created_by == actor.id:
            result.append(delegation)
            continue
        if delegation.scope == ORG_UNIT:
            if delegation.target_org_unit_id in visible_units:
                result.append(delegation)
        else:
            target = db.get(User, delegation.target_user_id)
            if target is not None and target.org_unit_id in visible_units:
                result.append(delegation)
    return result


def can_act_for(db: Session, actor: User, target_user_id: uuid.UUID) -> bool:
    if actor.id == target_user_id:
        return True
    if permissions.resolve_role(db, actor) == permissions.HR_ADMIN:
        return True

    direct = db.scalar(
        select(LeaveDelegation.id).where(
            LeaveDelegation.delegate_user_id == actor.id,
            LeaveDelegation.scope == USER,
            LeaveDelegation.target_user_id == target_user_id,
            LeaveDelegation.is_active,
        )
    )
    if direct is not None:
        return True

    target = db.get(User, target_user_id)
    if target is None or target.org_unit_id is None:
        return False

    unit_ids = db.scalars(
        select(LeaveDelegation.target_org_unit_id).where(
            LeaveDelegation.delegate_user_id == actor.id,
            LeaveDelegation.scope == ORG_UNIT,
            LeaveDelegation.is_active,
        )
    ).all()
    return any(
        target.org_unit_id in org_unit_service.descendant_ids(db, unit_id) for unit_id in unit_ids
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
    список для переключателя "от чьего имени" в UI. Объединяет прямые
    (scope=user) и подразделенческие (scope=org_unit, с каскадом на
    нижестоящие) делегирования."""
    direct = list(
        db.scalars(
            select(User)
            .join(LeaveDelegation, LeaveDelegation.target_user_id == User.id)
            .where(
                LeaveDelegation.delegate_user_id == delegate.id,
                LeaveDelegation.scope == USER,
                LeaveDelegation.is_active,
            )
        ).all()
    )

    unit_ids = db.scalars(
        select(LeaveDelegation.target_org_unit_id).where(
            LeaveDelegation.delegate_user_id == delegate.id,
            LeaveDelegation.scope == ORG_UNIT,
            LeaveDelegation.is_active,
        )
    ).all()
    member_unit_ids: set[uuid.UUID] = set()
    for unit_id in unit_ids:
        member_unit_ids.update(org_unit_service.descendant_ids(db, unit_id))
    unit_members = (
        list(
            db.scalars(
                select(User).where(User.org_unit_id.in_(member_unit_ids), User.is_active)
            ).all()
        )
        if member_unit_ids
        else []
    )

    by_id = {u.id: u for u in direct + unit_members}
    by_id.pop(delegate.id, None)
    return sorted(by_id.values(), key=lambda u: u.full_name)
