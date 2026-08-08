import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.external_id_mapping import ExternalIdMapping
from app.models.org_unit import OrgUnit
from app.models.sync import SyncChangeLog, SyncRun
from app.models.user import User
from app.sync.dto import ExternalOrgUnitDTO, ExternalUserDTO
from app.sync.interface import ExternalDirectoryClient

ORG_UNIT = "org_unit"
USER = "user"


def _get_or_create_mapping(
    db: Session, entity_type: str, external_system: str, external_id: str
) -> uuid.UUID:
    """Резолвит внутренний ID для внешней сущности, создавая маппинг при первом
    появлении. Разделение "выдать ID" и "создать/обновить строку" — то, что
    позволяет разрешать циклические FK между org_units и users без спецхаков
    на уровне ORM (см. sync_service.run_sync)."""
    mapping = db.scalar(
        select(ExternalIdMapping).where(
            ExternalIdMapping.entity_type == entity_type,
            ExternalIdMapping.external_system == external_system,
            ExternalIdMapping.external_id == external_id,
        )
    )
    if mapping is not None:
        return mapping.internal_id

    internal_id = uuid.uuid4()
    db.add(
        ExternalIdMapping(
            entity_type=entity_type,
            external_system=external_system,
            external_id=external_id,
            internal_id=internal_id,
        )
    )
    return internal_id


def _diff_fields(before: dict | None, after: dict) -> tuple[str, dict]:
    if before is None:
        return "created", {}
    changed = {
        field: {"before": before.get(field), "after": value}
        for field, value in after.items()
        if before.get(field) != value
    }
    return ("updated", changed) if changed else ("unchanged", {})


def run_sync(
    db: Session,
    client: ExternalDirectoryClient,
    trigger_type: str,
    triggered_by: uuid.UUID | None,
) -> SyncRun:
    run = SyncRun(trigger_type=trigger_type, triggered_by=triggered_by, status="running")
    db.add(run)
    db.flush()

    summary = {
        "org_units": {"created": 0, "updated": 0, "unchanged": 0},
        "users": {"created": 0, "updated": 0, "unchanged": 0},
    }
    change_entries: list[tuple[str, str, uuid.UUID, dict]] = []  # entity_type, ext_id, internal_id, before

    try:
        org_unit_dtos = client.fetch_org_units()
        user_dtos = client.fetch_users()

        org_unit_ids = {
            dto.external_id: _get_or_create_mapping(db, ORG_UNIT, client.system_name, dto.external_id)
            for dto in org_unit_dtos
        }
        user_ids = {
            dto.external_id: _get_or_create_mapping(db, USER, client.system_name, dto.external_id)
            for dto in user_dtos
        }
        db.flush()

        # Pass 1: org_units — name/unit_kind/parent_id. head_user_id оставляем
        # нетронутым (кросс-табличный цикл с users, см. модель) — резолвится в pass 3.
        org_unit_before: dict[str, dict | None] = {}
        for dto in org_unit_dtos:
            internal_id = org_unit_ids[dto.external_id]
            existing = db.get(OrgUnit, internal_id)
            org_unit_before[dto.external_id] = (
                {
                    "name": existing.name,
                    "unit_kind": existing.unit_kind,
                    "parent_id": str(existing.parent_id) if existing.parent_id else None,
                }
                if existing
                else None
            )
            parent_id = org_unit_ids.get(dto.parent_external_id) if dto.parent_external_id else None
            if existing is None:
                db.add(
                    OrgUnit(
                        id=internal_id,
                        name=dto.name,
                        unit_kind=dto.unit_kind,
                        parent_id=parent_id,
                        is_active=True,
                    )
                )
            else:
                existing.name = dto.name
                existing.unit_kind = dto.unit_kind
                existing.parent_id = parent_id
                existing.is_active = True
        db.flush()

        # Pass 2: users — org_unit_id уже резолвим (org_units существуют).
        user_before: dict[str, dict | None] = {}
        for dto in user_dtos:
            internal_id = user_ids[dto.external_id]
            existing = db.get(User, internal_id)
            user_before[dto.external_id] = (
                {
                    "email": existing.email,
                    "full_name": existing.full_name,
                    "org_unit_id": str(existing.org_unit_id) if existing.org_unit_id else None,
                    "has_benefits": existing.has_benefits,
                    "is_active": existing.is_active,
                }
                if existing
                else None
            )
            org_unit_id = (
                org_unit_ids.get(dto.org_unit_external_id) if dto.org_unit_external_id else None
            )
            now = datetime.now(timezone.utc)
            if existing is None:
                db.add(
                    User(
                        id=internal_id,
                        email=dto.email,
                        full_name=dto.full_name,
                        org_unit_id=org_unit_id,
                        has_benefits=dto.has_benefits,
                        is_active=dto.is_active,
                        last_synced_at=now,
                    )
                )
            else:
                existing.email = dto.email
                existing.full_name = dto.full_name
                existing.org_unit_id = org_unit_id
                existing.has_benefits = dto.has_benefits
                existing.is_active = dto.is_active
                existing.last_synced_at = now
        db.flush()

        # Pass 3: head_user_id — теперь users существуют.
        org_unit_after: dict[str, dict] = {}
        for dto in org_unit_dtos:
            internal_id = org_unit_ids[dto.external_id]
            org_unit_row = db.get(OrgUnit, internal_id)
            head_user_id = (
                user_ids.get(dto.head_external_id) if dto.head_external_id else None
            )
            before = org_unit_before[dto.external_id]
            if before is not None:
                before["head_user_id"] = (
                    str(org_unit_row.head_user_id) if org_unit_row.head_user_id else None
                )
            org_unit_row.head_user_id = head_user_id
            org_unit_after[dto.external_id] = {
                "name": org_unit_row.name,
                "unit_kind": org_unit_row.unit_kind,
                "parent_id": str(org_unit_row.parent_id) if org_unit_row.parent_id else None,
                "head_user_id": str(org_unit_row.head_user_id) if org_unit_row.head_user_id else None,
            }
        db.flush()

        for dto in org_unit_dtos:
            change_type, diff = _diff_fields(
                org_unit_before[dto.external_id], org_unit_after[dto.external_id]
            )
            summary["org_units"][change_type] += 1
            change_entries.append((ORG_UNIT, dto.external_id, org_unit_ids[dto.external_id], diff, change_type))

        for dto in user_dtos:
            after = {
                "email": dto.email,
                "full_name": dto.full_name,
                "org_unit_id": str(org_unit_ids.get(dto.org_unit_external_id))
                if dto.org_unit_external_id
                else None,
                "has_benefits": dto.has_benefits,
                "is_active": dto.is_active,
            }
            change_type, diff = _diff_fields(user_before[dto.external_id], after)
            summary["users"][change_type] += 1
            change_entries.append((USER, dto.external_id, user_ids[dto.external_id], diff, change_type))

        for entity_type, external_id, internal_id, diff, change_type in change_entries:
            db.add(
                SyncChangeLog(
                    sync_run_id=run.id,
                    entity_type=entity_type,
                    external_id=external_id,
                    internal_id=internal_id,
                    change_type=change_type,
                    diff=diff,
                )
            )

        run.status = "success"
    except Exception as exc:  # noqa: BLE001 — фиксируем любую ошибку синка в run, не роняем процесс
        run.status = "failed"
        run.error_message = str(exc)

    run.summary = summary
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run
