import pytest

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models.user import User
from app.services import org_unit_service


def test_create_org_unit(db_session):
    unit = org_unit_service.create(db_session, "Отдел продаж", "отдел", None, None)
    assert unit.id is not None
    assert unit.is_active is True


def test_create_rejects_unknown_parent(db_session):
    import uuid

    with pytest.raises(NotFoundError):
        org_unit_service.create(db_session, "Отдел", None, uuid.uuid4(), None)


def test_update_renames_and_reparents(db_session):
    parent = org_unit_service.create(db_session, "Управление", None, None, None)
    child = org_unit_service.create(db_session, "Отдел", None, None, None)

    updated = org_unit_service.update(
        db_session, child.id, "Отдел (переименован)", "отдел", parent.id, None, True
    )
    assert updated.name == "Отдел (переименован)"
    assert updated.parent_id == parent.id


def test_update_rejects_self_as_parent(db_session):
    unit = org_unit_service.create(db_session, "Отдел", None, None, None)
    with pytest.raises(ValidationFailedError):
        org_unit_service.update(db_session, unit.id, "Отдел", None, unit.id, None, True)


def test_update_rejects_cycle_via_descendant(db_session):
    parent = org_unit_service.create(db_session, "Управление", None, None, None)
    child = org_unit_service.create(db_session, "Отдел", None, parent.id, None)

    with pytest.raises(ValidationFailedError):
        org_unit_service.update(db_session, parent.id, "Управление", None, child.id, None, True)


def test_deactivate_blocked_by_active_children(db_session):
    parent = org_unit_service.create(db_session, "Управление", None, None, None)
    org_unit_service.create(db_session, "Отдел", None, parent.id, None)

    with pytest.raises(ValidationFailedError):
        org_unit_service.deactivate(db_session, parent.id)


def test_deactivate_blocked_by_active_employees(db_session):
    unit = org_unit_service.create(db_session, "Отдел", None, None, None)
    user = User(email="e@d.local", full_name="E", org_unit_id=unit.id)
    db_session.add(user)
    db_session.flush()

    with pytest.raises(ValidationFailedError):
        org_unit_service.deactivate(db_session, unit.id)


def test_deactivate_succeeds_when_empty(db_session):
    unit = org_unit_service.create(db_session, "Отдел", None, None, None)
    deactivated = org_unit_service.deactivate(db_session, unit.id)
    assert deactivated.is_active is False
