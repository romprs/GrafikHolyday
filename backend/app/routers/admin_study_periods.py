from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select

from app.core.exceptions import ValidationFailedError
from app.dependencies import DbSession, require_role
from app.integrations.study_periods import StudyPeriodsClient
from app.models.sync import KIND_STUDY_PERIODS, SyncRun
from app.models.user import User
from app.schemas.study_periods_test import StudyPeriodsTestIn, StudyPeriodsTestResultOut
from app.schemas.sync import SyncRunOut
from app.services import (
    permissions,
    restriction_settings_service,
    study_period_sync_service,
    sync_service,
)

MAX_TEST_EMPLOYEE_CODES = 5

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
    client = study_period_sync_service.build_client(db)
    if client is None:
        raise ValidationFailedError(
            "Источник не настроен, выключен, не задан URL, или включён режим "
            "«файл» — для него используйте загрузку файла, а не запуск синхронизации"
        )
    year = restriction_settings_service.get_planning_year(db)
    return study_period_sync_service.run_http_sync(
        db, client, date(year, 1, 1), date(year, 12, 31), "manual", user.id
    )


@router.post("/test", response_model=list[StudyPeriodsTestResultOut])
def test_study_periods_connection(
    body: StudyPeriodsTestIn, db: DbSession, _: HrAdmin
) -> list[StudyPeriodsTestResultOut]:
    """Тестовое подключение — на 1-5 табельных номерах, без записи в БД
    (никакой SyncRun/BlockedPeriod). Реквизиты берутся прямо из тела
    запроса (то, что сейчас в форме, необязательно уже сохранённое) —
    чтобы можно было проверить новый URL/логин до сохранения. Возвращает
    сформированный запрос и сырой ответ на каждый номер — именно то, чего
    не видно в обычной истории синка, где при сбое просто "ошибок
    запроса: N" без деталей."""
    if not body.employee_codes:
        raise ValidationFailedError("Укажите хотя бы один табельный номер")
    if len(body.employee_codes) > MAX_TEST_EMPLOYEE_CODES:
        raise ValidationFailedError(
            f"Не больше {MAX_TEST_EMPLOYEE_CODES} табельных номеров за один тест"
        )
    if not body.base_url.strip():
        raise ValidationFailedError("Не задан URL источника")

    year = restriction_settings_service.get_planning_year(db)
    period_from = body.period_from or date(year, 1, 1)
    period_to = body.period_to or date(year, 12, 31)

    client = StudyPeriodsClient(
        base_url=body.base_url,
        login=body.auth_login,
        password=body.auth_password,
        verify_tls=body.verify_tls,
    )
    return [
        StudyPeriodsTestResultOut(**client.test_fetch(code.strip(), period_from, period_to))
        for code in body.employee_codes
        if code.strip()
    ]


@router.get("/runs", response_model=list[SyncRunOut])
def list_study_periods_runs(db: DbSession, _: HrAdmin) -> list[SyncRunOut]:
    return list(
        db.scalars(
            select(SyncRun)
            .where(SyncRun.kind == KIND_STUDY_PERIODS)
            .order_by(SyncRun.started_at.desc())
        ).all()
    )


@router.delete("/runs", status_code=204)
def clear_study_periods_runs(db: DbSession, _: HrAdmin) -> None:
    sync_service.clear_history(db, KIND_STUDY_PERIODS)
