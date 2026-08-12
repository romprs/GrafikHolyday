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


def test_beneficiary_flag_parsed():
    raw = [{"DaysCount": 44, "L": "Да"}]
    entry = parse_vacation_days(raw)
    assert entry.is_beneficiary is True


def test_empty_response_returns_none():
    assert parse_vacation_days([]) is None


def test_malformed_entry_returns_none():
    assert parse_vacation_days([{"foo": "bar"}]) is None
