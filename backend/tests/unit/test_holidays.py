from datetime import date

from app.core.holidays import count_leave_days, is_holiday


def test_holiday_inside_leave_is_not_counted():
    # 1–14 июня 2026: 12 июня — праздник, значит списывается 13 дней, а не 14
    assert count_leave_days(date(2026, 6, 1), date(2026, 6, 14)) == 13


def test_new_year_eve_is_non_working():
    assert is_holiday(date(2026, 12, 31))
    assert count_leave_days(date(2026, 12, 28), date(2026, 12, 31)) == 3


def test_period_without_holidays_counts_all_days():
    assert count_leave_days(date(2026, 7, 1), date(2026, 7, 14)) == 14
