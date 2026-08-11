import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

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
