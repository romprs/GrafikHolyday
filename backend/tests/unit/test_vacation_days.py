from datetime import date

from app.integrations.vacation_days import parse_vacation_days


def test_parses_standard_entry():
    raw = [
        {
            "Employee": "Королёв Кирилл Сергеевич",
            "Podr": "Отдел контрактного сопровождения",
            "Position": "Ведущий специалист",
            "DaysCount": 36,
            "L": "Нет",
            "Kat": "Специалисты",
        }
    ]
    entry = parse_vacation_days(raw)
    assert entry is not None
    assert entry.days_count == 36
    assert entry.is_beneficiary is False
    assert entry.hire_date is None
    assert entry.termination_date is None


def test_parses_hire_and_dismissal_dates_dotted_format():
    raw = [{"DaysCount": 28, "L": "Нет", "HireDate": "01.09.2027", "DismissalDate": None}]
    entry = parse_vacation_days(raw)
    assert entry.hire_date == date(2027, 9, 1)
    assert entry.termination_date is None


def test_parses_hire_and_dismissal_dates_iso_format():
    # На случай, если источник (как это уже было со study_periods, Phase
    # 6.33) на практике отдаст ISO 8601 вместо задокументированного формата.
    raw = [{"DaysCount": 28, "L": "Нет", "HireDate": "2027-09-01T00:00:00", "DismissalDate": "2028-03-15"}]
    entry = parse_vacation_days(raw)
    assert entry.hire_date == date(2027, 9, 1)
    assert entry.termination_date == date(2028, 3, 15)


def test_empty_dismissal_date_string_treated_as_none():
    raw = [{"DaysCount": 28, "L": "Нет", "HireDate": "01.09.2027", "DismissalDate": ""}]
    entry = parse_vacation_days(raw)
    assert entry.termination_date is None


def test_beneficiary_flag_parsed():
    raw = [{"DaysCount": 44, "L": "Да"}]
    entry = parse_vacation_days(raw)
    assert entry.is_beneficiary is True


def test_empty_response_returns_none():
    assert parse_vacation_days([]) is None


def test_malformed_entry_returns_none():
    assert parse_vacation_days([{"foo": "bar"}]) is None
