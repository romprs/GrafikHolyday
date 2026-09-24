import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# JSON на SQLite (unit-тесты) — JSONB нативно только для Postgres.
_JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class RestrictionSettings(Base):
    """Управляемые ограничения (мин. длительность, блокировки, пороги загруженности).

    Natural key (не UUID) — записи создаются кодом через сиды, а не пользователем.
    """

    __tablename__ = "restriction_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    params: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )


MIN_LEAVE_DURATION = "min_leave_duration"
BLOCKED_PERIOD_ENFORCEMENT = "blocked_period_enforcement"
DEPARTMENT_LOAD_THRESHOLDS = "department_load_thresholds"
LEAVE_BALANCE_LIMIT = "leave_balance_limit"
OWN_OVERLAP_CHECK = "own_overlap_check"
# Не ограничение (enabled/exemptable для неё не имеют смысла) — общий параметр
# приложения, но хранится в той же таблице/API, чтобы не заводить отдельный
# механизм настроек ради одного значения.
PLANNING_YEAR = "planning_year"
# Порог длительности отпуска (в днях), после которого можно запросить
# выплату ЕСВ к отпуску. enabled=False отключает программу целиком.
VACATION_BONUS = "vacation_bonus"
# Два НЕЗАВИСИМЫХ ограничения на выплату ЕСВ по стажу (разные механики,
# разные группы сотрудников — включаются/выключаются раздельно, отдельные
# настройки, а не два параметра одной):
# - новичкам (стаж < года): ЕСВ доступна не раньше params["months"] месяцев
#   с даты приёма (User.hire_date) — одноразовый порог;
# - стажистам (стаж >= года): ежегодно повторяющееся ограничение по месяцу
#   приёма и текущему плановому году — см. leave_request_service._veteran_cutoff.
# enabled=False у каждой отключает именно её (программа ЕСВ в целом
# продолжает работать по порогу VACATION_BONUS).
VACATION_BONUS_NEW_HIRE = "vacation_bonus_new_hire_restriction"
VACATION_BONUS_VETERAN = "vacation_bonus_veteran_restriction"
# Параметры подключения к внешней системе-источнику оргструктуры (отделы) —
# редактируется в админке, реальный клиент см. app/integrations/org_directory.py.
EXTERNAL_SOURCE_CONNECTION = "external_source_connection"
# Параметры авторизации (режим dev/oidc и реквизиты OIDC-провайдера).
AUTH_CONFIGURATION = "auth_configuration"
# Подключение к источнику учебных планов (недоступные периоды сотрудников) —
# см. app/integrations/study_periods.py. Сопоставление с сотрудником — по
# табельному номеру (User.employee_code).
STUDY_PERIODS_SOURCE = "study_periods_source"
# Подключение к источнику остатка дней отпуска и признака льготника —
# см. app/integrations/vacation_days.py. Отдельная система от оргструктуры/
# сотрудников (drx) и от учебных планов; сопоставление тоже по табельному
# номеру.
VACATION_DAYS_SOURCE = "vacation_days_source"
