from datetime import date

import pytest

from app.core.exceptions import ForbiddenError, ValidationFailedError
from app.models.leave_balance import LeaveBalance
from app.models.leave_type import LeaveType
from app.models.restriction_settings import VACATION_BONUS, RestrictionSettings
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
        db_session, employee, date(2026, 6, 1), date(2026, 6, 20), None, bonus_requested=True
    )
    assert request.bonus_requested is True


def test_bonus_requested_for_short_period_rejected(db_session, employee, bonus_setting):
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, employee, date(2026, 6, 1), date(2026, 6, 10), None, bonus_requested=True
        )


def test_bonus_requested_below_threshold_rejected(db_session, employee, bonus_setting):
    # "14 и более" — 13 дней ещё не считается
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, employee, date(2026, 6, 1), date(2026, 6, 13), None, bonus_requested=True
        )


def test_bonus_requested_exactly_at_threshold_succeeds(db_session, employee, bonus_setting):
    # "14 и более" — ровно 14 уже считается
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 6, 1), date(2026, 6, 14), None, bonus_requested=True
    )
    assert request.bonus_requested is True


def test_bonus_requested_when_program_disabled_rejected(db_session, employee):
    db_session.add(RestrictionSettings(key=VACATION_BONUS, enabled=False, params={"min_days": 14}))
    db_session.flush()
    with pytest.raises(ValidationFailedError):
        leave_request_service.create_draft(
            db_session, employee, date(2026, 6, 1), date(2026, 6, 20), None, bonus_requested=True
        )


def test_no_bonus_requested_does_not_check_threshold(db_session, employee, bonus_setting):
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 6, 1), date(2026, 6, 5), None, bonus_requested=False
    )
    assert request.bonus_requested is False


def test_update_draft_bonus_toggles_after_creation(db_session, employee, bonus_setting):
    # Доплата запрашивается отдельным действием на уже добавленном черновике,
    # а не одновременно с выбором дат на календаре.
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 6, 1), date(2026, 6, 20), None
    )
    assert request.bonus_requested is False

    updated = leave_request_service.update_draft_bonus(db_session, employee, request.id, True)
    assert updated.bonus_requested is True

    updated_again = leave_request_service.update_draft_bonus(db_session, employee, request.id, False)
    assert updated_again.bonus_requested is False


def test_update_draft_bonus_rejects_short_period(db_session, employee, bonus_setting):
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 6, 1), date(2026, 6, 5), None
    )
    with pytest.raises(ValidationFailedError):
        leave_request_service.update_draft_bonus(db_session, employee, request.id, True)


def test_update_draft_bonus_rejects_non_draft(db_session, employee, bonus_setting):
    request = leave_request_service.create_draft(
        db_session, employee, date(2026, 6, 1), date(2026, 6, 20), None
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
            db_session, employee, date(2026, 6, 1), date(2026, 6, 20), None, bonus_requested=True
        )


def test_update_draft_bonus_rejects_second_period_while_first_marked(
    db_session, employee, bonus_setting
):
    first = leave_request_service.create_draft(
        db_session, employee, date(2026, 2, 1), date(2026, 2, 20), None, bonus_requested=True
    )
    second = leave_request_service.create_draft(
        db_session, employee, date(2026, 6, 1), date(2026, 6, 20), None
    )

    with pytest.raises(ValidationFailedError):
        leave_request_service.update_draft_bonus(db_session, employee, second.id, True)

    # Снять с первого — и второй становится доступен.
    leave_request_service.update_draft_bonus(db_session, employee, first.id, False)
    updated = leave_request_service.update_draft_bonus(db_session, employee, second.id, True)
    assert updated.bonus_requested is True
