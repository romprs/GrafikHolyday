import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models.org_unit import OrgUnit
from app.models.user import User
from app.services import permissions


def ancestor_ids(db: Session, org_unit_id: uuid.UUID) -> list[uuid.UUID]:
    """Цепочка предков (включая сам юнит), от узла к корню.

    Используется для разрешения блокировок: блок на org_unit действует на все
    дочерние подразделения, поэтому у сотрудника проверяется вся цепочка вверх
    от его юнита — дешевле, чем разворачивать потомков каждого блока вниз.
    """
    cte = (
        select(OrgUnit.id, OrgUnit.parent_id)
        .where(OrgUnit.id == org_unit_id)
        .cte(name="ancestors", recursive=True)
    )
    parent = cte.alias("parent")
    cte = cte.union_all(
        select(OrgUnit.id, OrgUnit.parent_id).where(OrgUnit.id == parent.c.parent_id)
    )
    return list(db.scalars(select(cte.c.id)).all())


def descendant_ids(db: Session, org_unit_id: uuid.UUID) -> list[uuid.UUID]:
    """Сам юнит и все его потомки любой глубины — для roll-up загруженности
    и распространения блокировок вниз по дереву."""
    cte = (
        select(OrgUnit.id)
        .where(OrgUnit.id == org_unit_id)
        .cte(name="descendants", recursive=True)
    )
    child = cte.alias("child")
    cte = cte.union_all(select(OrgUnit.id).where(OrgUnit.parent_id == child.c.id))
    return list(db.scalars(select(cte.c.id)).all())


def headed_unit_ids(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(select(OrgUnit.id).where(OrgUnit.head_user_id == user_id)).all())


def visible_unit_ids(db: Session, user: User) -> list[uuid.UUID] | None:
    """Подразделения, видимые пользователю — руководитель видит свой юнит и
    всё, что ниже (каскад по управлению), но не то, что выше или в стороне;
    вышестоящий руководитель за счёт этого автоматически видит всё, что
    видят его подчинённые руководители. HR/админ видит всё — возвращает
    None (means "без фильтра"), а не полный список: длиннее и дороже
    выбирать все id только чтобы тут же снять фильтр по ним.
    """
    role = permissions.resolve_role(db, user)
    if role == permissions.HR_ADMIN:
        return None
    if role != permissions.MANAGER:
        return []

    unit_ids: set[uuid.UUID] = set()
    for unit_id in headed_unit_ids(db, user.id):
        unit_ids.update(descendant_ids(db, unit_id))
    return list(unit_ids)


def create(
    db: Session,
    name: str,
    unit_kind: str | None,
    parent_id: uuid.UUID | None,
    head_user_id: uuid.UUID | None,
) -> OrgUnit:
    """Ручное создание подразделения HR — наравне с теми, что приходят из
    синхронизации оргструктуры (см. app/integrations/org_directory.py):
    у синка нет собственного маппинга на такие юниты, поэтому он их не
    трогает и не может случайно перезаписать."""
    if parent_id is not None and db.get(OrgUnit, parent_id) is None:
        raise NotFoundError("Родительское подразделение не найдено")
    unit = OrgUnit(name=name, unit_kind=unit_kind, parent_id=parent_id, head_user_id=head_user_id)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


def update(
    db: Session,
    unit_id: uuid.UUID,
    name: str,
    unit_kind: str | None,
    parent_id: uuid.UUID | None,
    head_user_id: uuid.UUID | None,
    is_active: bool,
) -> OrgUnit:
    unit = db.get(OrgUnit, unit_id)
    if unit is None:
        raise NotFoundError("Подразделение не найдено")

    if parent_id is not None:
        if parent_id == unit_id:
            raise ValidationFailedError("Подразделение не может быть родителем самому себе")
        if db.get(OrgUnit, parent_id) is None:
            raise NotFoundError("Родительское подразделение не найдено")
        if parent_id in descendant_ids(db, unit_id):
            raise ValidationFailedError(
                "Нельзя сделать родителем собственное подчинённое подразделение — получится цикл"
            )

    if not is_active and unit.is_active:
        active_children = db.scalar(
            select(OrgUnit.id).where(OrgUnit.parent_id == unit_id, OrgUnit.is_active)
        )
        if active_children is not None:
            raise ValidationFailedError(
                "Нельзя деактивировать подразделение, пока в нём есть активные дочерние "
                "подразделения — сначала перенесите или деактивируйте их"
            )
        active_employees = db.scalar(
            select(User.id).where(User.org_unit_id == unit_id, User.is_active)
        )
        if active_employees is not None:
            raise ValidationFailedError(
                "Нельзя деактивировать подразделение, пока в нём есть сотрудники — "
                "сначала перенесите их в другое подразделение"
            )

    unit.name = name
    unit.unit_kind = unit_kind
    unit.parent_id = parent_id
    unit.head_user_id = head_user_id
    unit.is_active = is_active
    db.commit()
    db.refresh(unit)
    return unit


def deactivate(db: Session, unit_id: uuid.UUID) -> OrgUnit:
    unit = db.get(OrgUnit, unit_id)
    if unit is None:
        raise NotFoundError("Подразделение не найдено")
    return update(
        db, unit_id, unit.name, unit.unit_kind, unit.parent_id, unit.head_user_id, is_active=False
    )
