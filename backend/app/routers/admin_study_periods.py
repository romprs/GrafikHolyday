from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select

from app.core.exceptions import ValidationFailedError
from app.dependencies import DbSession, require_role
from app.integrations.study_periods import StudyPeriodsClient
from app.models.restriction_settings import STUDY_PERIODS_SOURCE
from app.models.sync import KIND_STUDY_PERIODS, SyncRun
from app.models.user import User
from app.schemas.sync import SyncRunOut
from app.services import permissions, restriction_settings_service, study_period_sync_service

router = APIRouter(prefix="/admin/study-periods", tags=["admin-study-periods"])

HrAdmin = Annotated[User, Depends(require_role(permissions.HR_ADMIN))]


@router.post("/import", response_model=SyncRunOut)
def import_study_periods_file(
    db: DbSession, user: HrAdmin, raw: list[dict] = Body(...)
) -> SyncRunOut:
    if not raw:
        raise ValidationFailedError("Файл не содержит записей")
    return study_period_sync_service.run_file_import(db, raw, "manual", user.id)


@router.post("/run", response_model=SyncRunOut)
def trigger_study_periods_sync(db: DbSession, user: HrAdmin) -> SyncRunOut:
    setting = restriction_settings_service.get(db, STUDY_PERIODS_SOURCE)
    if setting is None or not setting.enabled:
        raise ValidationFailedError("Источник учебных планов не настроен или выключен")
    params = setting.params
    if params.get("mode") != "http":
        raise ValidationFailedError(
            "Ручной запуск синхронизации доступен только в режиме HTTP-источника — "
            "для файла используйте импорт"
        )
    base_url = params.get("base_url") or ""
    if not base_url:
        raise ValidationFailedError("Не задан URL источника учебных планов")

    try:
        client = StudyPeriodsClient(
            base_url=base_url,
            login=params.get("auth_login") or "",
            password=params.get("auth_password") or "",
            verify_tls=bool(params.get("verify_tls", False)),
            cert_path=params.get("cert_path") or None,
            cert_password=params.get("cert_password") or None,
        )
    except (OSError, RuntimeError) as exc:
        # Битый/отсутствующий путь к сертификату — частая ошибка при первой
        # настройке, показываем её сразу в UI, а не 500-й без деталей.
        raise ValidationFailedError(f"Не удалось подготовить клиент источника: {exc}") from exc
    year = restriction_settings_service.get_planning_year(db)
    return study_period_sync_service.run_http_sync(
        db, client, date(year, 1, 1), date(year, 12, 31), "manual", user.id
    )


@router.get("/runs", response_model=list[SyncRunOut])
def list_study_periods_runs(db: DbSession, _: HrAdmin) -> list[SyncRunOut]:
    return list(
        db.scalars(
            select(SyncRun)
            .where(SyncRun.kind == KIND_STUDY_PERIODS)
            .order_by(SyncRun.started_at.desc())
        ).all()
    )
