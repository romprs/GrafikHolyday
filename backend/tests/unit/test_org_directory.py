from app.integrations.org_directory import parse_departments


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
