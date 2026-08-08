import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.org_unit import OrgUnit


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
