from app.integrations.org_directory import parse_departments, parse_employees


def test_parses_basic_records():
    value = "4577#Автоматическая станция налива#1007#490#828|490#Производство № 4#534#706#828|"
    dtos = parse_departments(value)
    assert len(dtos) == 2

    first = dtos[0]
    assert first.external_id == "4577"
    assert first.name == "Автоматическая станция налива"
    assert first.head_external_id == "1007"
    assert first.parent_external_id == "490"


def test_zero_refs_become_none():
    value = "1#Корень#0#0#0"
    dtos = parse_departments(value)
    assert dtos[0].head_external_id is None
    assert dtos[0].parent_external_id is None


def test_trailing_and_empty_chunks_ignored():
    value = "1#A#0#0#0||  |"
    dtos = parse_departments(value)
    assert len(dtos) == 1


def test_short_malformed_record_skipped():
    value = "1#A#0#0#0|justtwo#fields"
    dtos = parse_departments(value)
    assert len(dtos) == 1
    assert dtos[0].external_id == "1"


def test_parses_employees():
    value = (
        "8898#Королёв Кирилл Сергеевич#6378#107#KSKorolev@corp.amurgpz.ru"
        "|100#Волкова Анна Алексеевна#100#73#AAVolkova@corp.amurgpz.ru"
    )
    dtos = parse_employees(value)
    assert len(dtos) == 2

    first = dtos[0]
    assert first.external_id == "8898"
    assert first.full_name == "Королёв Кирилл Сергеевич"
    assert first.employee_code == "6378"
    assert first.org_unit_external_id == "107"
    assert first.email == "kskorolev@corp.amurgpz.ru"


def test_employees_without_login_are_skipped():
    value = "8602#Сенников Сергей Владимирович#6213#6358#|100#Волкова Анна Алексеевна#100#73#a@b.ru"
    dtos = parse_employees(value)
    assert len(dtos) == 1
    assert dtos[0].external_id == "100"


def test_employees_short_record_skipped():
    value = "1#A#100#1#a@b.ru|too#short"
    dtos = parse_employees(value)
    assert len(dtos) == 1
