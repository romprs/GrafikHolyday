import uuid
from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.blocked_period import GLOBAL, ORG_UNIT, USER, BlockedPeriod
from app.models.org_unit import OrgUnit
from app.models.user import User
from app.services import org_unit_service, permissions


def get_effective_blocks(
    db: Session, user: User, date_from: date, date_to: date
) -> list[BlockedPeriod]:
    """Активные блокировки, пересекающиеся с диапазоном и применимые к пользователю:
    глобальные, на любой юнит из его цепочки предков, или персональные."""
    unit_ids = org_unit_service.ancestor_ids(db, user.org_unit_id) if user.org_unit_id else []

    scope_filter = or_(
        BlockedPeriod.scope == GLOBAL,
        and_(BlockedPeriod.scope == ORG_UNIT, BlockedPeriod.org_unit_id.in_(unit_ids)),
        and_(BlockedPeriod.scope == USER, BlockedPeriod.user_id == user.id),
    )
    return list(
        db.scalars(
            select(BlockedPeriod).where(
                BlockedPeriod.is_active,
                scope_filter,
                BlockedPeriod.date_from <= date_to,
                BlockedPeriod.date_to >= date_from,
            )
        ).all()
    )


def list_all(db: Session) -> list[BlockedPeriod]:
    return list(
        db.scalars(
            select(BlockedPeriod)
            .where(BlockedPeriod.is_active)
            .order_by(BlockedPeriod.date_from)
        ).all()
    )


def _check_can_manage(db: Session, actor: User, scope: str, org_unit_id, user_id) -> None:
    role = permissions.resolve_role(db, actor)
    if role == permissions.HR_ADMIN:
        return
    if role != permissions.MANAGER:
        raise ForbiddenError("Недостаточно прав для управления недоступными периодами")

    # Каскад по иерархии (как в approval_service/org_unit_service), а не
    # только буквально свой юнит — иначе вышестоящий руководитель не мог
    # управлять блокировками нижестоящих отделов, и на практике это могли
    # делать только HR/админ, хотя UI показывал форму всем руководителям.
    managed_unit_ids = set(org_unit_service.visible_unit_ids(db, actor) or [])

    if scope == GLOBAL:
        raise ForbiddenError("Глобальные блокировки может создавать только HR/админ")
    if scope == ORG_UNIT:
        if org_unit_id not in managed_unit_ids:
            raise ForbiddenError("Можно управлять блокировками только своего отдела и подчинённых ему")
    if scope == USER:
        target = db.get(User, user_id)
        if target is None or target.org_unit_id is None:
            raise ForbiddenError("Сотрудник не найден")
        if target.org_unit_id not in managed_unit_ids:
            raise ForbiddenError("Можно управлять блокировками только своих сотрудников")


def create(
    db: Session,
    actor: User,
    date_from: date,
    date_to: date,
    reason: str,
    scope: str,
    org_unit_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
) -> BlockedPeriod:
    _check_can_manage(db, actor, scope, org_unit_id, user_id)

    blocked_period = BlockedPeriod(
        date_from=date_from,
        date_to=date_to,
        reason=reason,
        scope=scope,
        org_unit_id=org_unit_id,
        user_id=user_id,
        created_by=actor.id,
    )
    db.add(blocked_period)
    db.commit()
    db.refresh(blocked_period)
    return blocked_period


def deactivate(db: Session, actor: User, blocked_period_id: uuid.UUID) -> None:
    blocked_period = db.get(BlockedPeriod, blocked_period_id)
    if blocked_period is None:
        raise NotFoundError("Недоступный период не найден")
    _check_can_manage(
        db, actor, blocked_period.scope, blocked_period.org_unit_id, blocked_period.user_id
    )
    blocked_period.is_active = False
    db.commit()
