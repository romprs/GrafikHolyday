from datetime import date

import pytest

from app.core.exceptions import ForbiddenError, ValidationFailedError
from app.models.leave_balance import LeaveBalance
from app.models.leave_type import LeaveType
from app.models.restriction_settings import (
    PLANNING_YEAR,
    VACATION_BONUS,
    VACATION_BONUS_NEW_HIRE,
    VACATION_BONUS_VETERAN,
    RestrictionSettings,
)
from app.models.user import User
from app.services import leave_request_service


@pytest.fixture()
def employee(db_session):
    lt = LeaveType(code="vacation", name_ru="Отпуск")
    db_session.add(lt)
    user = User(email="bonus@test.local", full_name="Bonus")
    db_session.add(user)
    db_session.flush()
    db_session.add(LeaveBalance(user_id=user.id, year=2026, accrued_days=20))
    db_session.flush()
    return user


@pytest.fixture()
def bonus_setting(db_session):
    setting = RestrictionSettings(key=VACATION_BONUS, enabled=True, params={"min_days": 14})
    db_session.add(setting)
    db_session.flush()
    return setting


def test_bonus_requested_for_long_period_succeeds(db_session, employee, bonus_setting):
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 7, 1), date(2026, 7, 20), None, bonus_requested=True
    )
    assert request.bonus_requested is True


def test_bonus_requested_for_short_period_rejected(db_session, employee, bonus_setting):
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, employee, date(2026, 7, 1), date(2026, 7, 10), None, bonus_requested=True
        )


def test_bonus_requested_below_threshold_rejected(db_session, employee, bonus_setting):
    # "14 и более" — 13 дней ещё не считается
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, employee, date(2026, 7, 1), date(2026, 7, 13), None, bonus_requested=True
        )


def test_bonus_requested_exactly_at_threshold_succeeds(db_session, employee, bonus_setting):
    # "14 и более" — ровно 14 уже считается
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 7, 1), date(2026, 7, 14), None, bonus_requested=True
    )
    assert request.bonus_requested is True


def test_bonus_requested_when_program_disabled_rejected(db_session, employee):
    db_session.add(RestrictionSettings(key=VACATION_BONUS, enabled=False, params={"min_days": 14}))
    db_session.flush()
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, employee, date(2026, 7, 1), date(2026, 7, 20), None, bonus_requested=True
        )


def test_no_bonus_requested_does_not_check_threshold(db_session, employee, bonus_setting):
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 7, 1), date(2026, 7, 5), None, bonus_requested=False
    )
    assert request.bonus_requested is False


def test_update_draft_bonus_toggles_after_creation(db_session, employee, bonus_setting):
    # Доплата запрашивается отдельным действием на уже добавленном черновике,
    # а не одновременно с выбором дат на календаре.
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 7, 1), date(2026, 7, 20), None
    )
    assert request.bonus_requested is False

    updated = leave_request_service.update_draft_bonus(db_session, employee, request.id, True)
    assert updated.bonus_requested is True

    updated_again = leave_request_service.update_draft_bonus(db_session, employee, request.id, False)
    assert updated_again.bonus_requested is False


def test_update_draft_bonus_rejects_short_period(db_session, employee, bonus_setting):
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 7, 1), date(2026, 7, 5), None
    )
    with pytest.raises(ValidationFailedError):
        leave_request_service.update_draft_bonus(db_session, employee, request.id, True)


def test_update_draft_bonus_rejects_non_draft(db_session, employee, bonus_setting):
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 7, 1), date(2026, 7, 20), None
    )
    leave_request_service.submit_drafts(db_session, employee, 2026)
    db_session.refresh(request)
    with pytest.raises(ForbiddenError):
        leave_request_service.update_draft_bonus(db_session, employee, request.id, True)


def test_bonus_only_on_one_period_per_plan(db_session, employee, bonus_setting):
    first = leave_request_service.create_draft(
        db_session, employee, date(2026, 2, 1), date(2026, 2, 20), None, bonus_requested=True
    )
    assert first.bonus_requested is True

    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, employee, date(2026, 7, 1), date(2026, 7, 20), None, bonus_requested=True
        )


def test_update_draft_bonus_rejects_second_period_while_first_marked(
    db_session, employee, bonus_setting
):
    first = leave_request_service.create_draft(
        db_session, employee, date(2026, 2, 1), date(2026, 2, 20), None, bonus_requested=True
    )
    second = leave_request_service.create_draft(
        db_session, employee, date(2026, 7, 1), date(2026, 7, 20), None
    )

    with pytest.raises(ValidationFailedError):
        leave_request_service.update_draft_bonus(db_session, employee, second.id, True)

    # Снять с первого — и второй становится доступен.
    leave_request_service.update_draft_bonus(db_session, employee, first.id, False)
    updated = leave_request_service.update_draft_bonus(db_session, employee, second.id, True)
    assert updated.bonus_requested is True


@pytest.fixture()
def tenure_setting(db_session):
    setting = RestrictionSettings(key=VACATION_BONUS_NEW_HIRE, enabled=True, params={"months": 10})
    db_session.add(setting)
    db_session.flush()
    return setting


def test_bonus_rejected_before_tenure_threshold(db_session, employee, bonus_setting, tenure_setting):
    # Принят 2026-01-01, порог 10 мес. -> доступно с 2026-11-01. Планируемый
    # период (2026-10-01) — раньше порога и раньше годовой отметки, значит
    # действует правило для новичков и оно должно блокировать.
    employee.hire_date = date(2026, 1, 1)
    db_session.flush()
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, employee, date(2026, 10, 1), date(2026, 10, 20), None, bonus_requested=True
        )


def test_bonus_allowed_after_tenure_threshold(db_session, employee, bonus_setting, tenure_setting):
    # Тот же приём (2026-01-01, порог 10 мес. -> доступно с 2026-11-01), но
    # планируемый период (2026-12-01) уже после порога и всё ещё раньше
    # годовой отметки (2027-01-01) — новичковое правило пройдено.
    employee.hire_date = date(2026, 1, 1)
    db_session.flush()
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 12, 1), date(2026, 12, 20), None, bonus_requested=True
    )
    assert request.bonus_requested is True


def test_bonus_unrestricted_once_tenure_reaches_one_year(db_session, employee, bonus_setting):
    # Планируемый период (2025-06-01) — уже после годовой отметки с даты
    # приёма (2024-01-01 + 12 мес. = 2025-01-01), поэтому правило для
    # новичков (VACATION_BONUS_NEW_HIRE) для ЭТОГО периода не проверяется
    # вовсе (см. _validate_bonus_tenure), даже если его months формально
    # ещё не истёк бы для более раннего периода; правило для стажистов
    # (VACATION_BONUS_VETERAN) в этом тесте не настроено — тоже не действует.
    db_session.add(RestrictionSettings(key=VACATION_BONUS_NEW_HIRE, enabled=True, params={"months": 13}))
    employee.hire_date = date(2024, 1, 1)
    db_session.flush()
    request = leave_request_service.create_draft(
        db_session, employee, date(2025, 6, 1), date(2025, 6, 20), None, bonus_requested=True
    )
    assert request.bonus_requested is True


def test_bonus_tenure_check_skipped_without_hire_date(db_session, employee, bonus_setting, tenure_setting):
    assert employee.hire_date is None
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 7, 1), date(2026, 7, 20), None, bonus_requested=True
    )
    assert request.bonus_requested is True


def test_bonus_tenure_check_skipped_when_disabled(db_session, employee, bonus_setting):
    db_session.add(RestrictionSettings(key=VACATION_BONUS_NEW_HIRE, enabled=False, params={"months": 10}))
    employee.hire_date = date(2026, 5, 22)
    db_session.flush()
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 7, 1), date(2026, 7, 20), None, bonus_requested=True
    )
    assert request.bonus_requested is True


# Правило для "ветеранов" (стаж год и больше) — ежегодно повторяющееся,
# завязанное на плановый год и месяц приёма (в отличие от одноразового
# правила для новичков выше). Подтверждено пользователем на примерах:
# принят 12.07 (любого давнего года) -> доступно с 12.01 планового года;
# принят 12.12 -> доступно с 12.06 планового года; принят в июне или
# раньше -> без ограничений. Сравнение — с датой начала планируемого
# периода, не с date.today() (см. _validate_bonus_tenure) — план на год
# составляют заранее, поэтому и плановый год, и даты приёма/периода в
# тестах фиксированы, без привязки к дате реального запуска тестов.
@pytest.fixture()
def veteran_setting_and_year(db_session):
    planning_year = 2027
    db_session.add(RestrictionSettings(key=PLANNING_YEAR, enabled=True, params={"year": planning_year}))
    db_session.add(
        RestrictionSettings(key=VACATION_BONUS_VETERAN, enabled=True, params={"shift_months": 6})
    )
    db_session.flush()
    return planning_year


def test_veteran_hired_second_half_blocked_before_shifted_cutoff(
    db_session, employee, bonus_setting, veteran_setting_and_year
):
    employee.hire_date = date(2015, 7, 12)  # июль -> сдвиг на январь планового года (2027-01-12)
    db_session.flush()
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, employee, date(2027, 1, 1), date(2027, 1, 20), None, bonus_requested=True
        )


def test_veteran_hired_december_shifts_to_june(
    db_session, employee, bonus_setting, veteran_setting_and_year
):
    planning_year = veteran_setting_and_year
    employee.hire_date = date(2015, 12, 12)  # декабрь -> сдвиг на июнь планового года (2027-06-12)
    db_session.flush()
    with pytest.raises(ValidationFailedError) as exc_info:
        leave_request_service.create_draft(
            db_session, employee, date(2027, 6, 1), date(2027, 6, 20), None, bonus_requested=True
        )
    assert date(planning_year, 6, 12).isoformat() in str(exc_info.value)


def test_veteran_hired_first_half_unrestricted(
    db_session, employee, bonus_setting, veteran_setting_and_year
):
    employee.hire_date = date(2015, 6, 12)  # июнь -> без ограничений
    db_session.flush()
    request = leave_request_service.create_draft(
        db_session, employee, date(2027, 6, 1), date(2027, 6, 20), None, bonus_requested=True
    )
    assert request.bonus_requested is True


def test_new_hire_and_veteran_settings_toggle_independently(db_session, employee, bonus_setting):
    # Новичкам включено, стажистам выключено — стажист (стаж больше года,
    # принят во 2-й половине давнего года) не должен блокироваться,
    # несмотря на то, что общее правило по стажу в принципе включено.
    db_session.add(RestrictionSettings(key=VACATION_BONUS_NEW_HIRE, enabled=True, params={"months": 10}))
    db_session.add(RestrictionSettings(key=VACATION_BONUS_VETERAN, enabled=False, params={"shift_months": 6}))
    db_session.add(RestrictionSettings(key=PLANNING_YEAR, enabled=True, params={"year": 2027}))
    employee.hire_date = date(2015, 12, 12)
    db_session.flush()
    request = leave_request_service.create_draft(
        db_session, employee, date(2027, 6, 1), date(2027, 6, 20), None, bonus_requested=True
    )
    assert request.bonus_requested is True
