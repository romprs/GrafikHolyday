from datetime import date, timedelta

# Нерабочие праздничные дни (ст. 112 ТК РФ) + 31.12 (по требованию заказчика
# считается нерабочим). Переносы выходных по постановлениям не учитываются —
# те же правила, что в frontend/src/holidays.ts, держать в синхроне.
_HOLIDAYS_MD = {
    (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8),
    (2, 23), (3, 8), (5, 1), (5, 9), (6, 12), (11, 4), (12, 31),
}


def is_holiday(d: date) -> bool:
    return (d.month, d.day) in _HOLIDAYS_MD


def holidays_in_range(date_from: date, date_to: date) -> int:
    total = (date_to - date_from).days + 1
    return sum(1 for i in range(total) if is_holiday(date_from + timedelta(days=i)))


def count_leave_days(date_from: date, date_to: date) -> int:
    """Календарные дни отпуска за вычетом праздничных: праздник внутри
    отпуска не списывается с лимита (конец периода при этом не двигается)."""
    return (date_to - date_from).days + 1 - holidays_in_range(date_from, date_to)
