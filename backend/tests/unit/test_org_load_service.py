from datetime import date

import pytest

from app.models.leave_request import APPROVED, LeaveRequest
from app.models.leave_type import LeaveType
from app.models.org_unit import OrgUnit
from app.models.restriction_settings import DEPARTMENT_LOAD_THRESHOLDS, RestrictionSettings
from app.models.user import User
from app.services import org_load_service


@pytest.fixture()
def scenario(db_session):
    db_session.add(
        RestrictionSettings(
            key=DEPARTMENT_LOAD_THRESHOLDS, enabled=True, params={"yellow": 0.30, "red": 0.50}
        )
    )
    lt = LeaveType(code="vacation", name_ru="Отпуск")
    db_session.add(lt)
    db_session.flush()

    division = OrgUnit(name="Управление", is_active=True)
    db_session.add(division)
    db_session.flush()

    dept_a = OrgUnit(name="Отдел А", parent_id=division.id, is_active=True)
    dept_b = OrgUnit(name="Отдел Б", parent_id=division.id, is_active=True)
    db_session.add_all([dept_a, dept_b])
    db_session.flush()

    # Отдел А: 4 обычных сотрудника + 1 льготник
    users_a = [User(email=f"a{i}@t.local", full_name=f"a{i}", org_unit_id=dept_a.id) for i in range(4)]
    benefits_user = User(
        email="benefits@t.local", full_name="benefits", org_unit_id=dept_a.id, has_benefits=True
    )
    # Отдел Б: 2 сотрудника
    users_b = [User(email=f"b{i}@t.local", full_name=f"b{i}", org_unit_id=dept_b.id) for i in range(2)]
    db_session.add_all(users_a + [benefits_user] + users_b)
    db_session.flush()

    def approved_leave(user, d_from, d_to):
        db_session.add(
            LeaveRequest(
                user_id=user.id,
                leave_type_id=lt.id,
                date_from=d_from,
                date_to=d_to,
                status=APPROVED,
            )
        )

    # 1 из 4 в отпуске 10-12 июня в отделе А -> 25% (green, <30%)
    approved_leave(users_a[0], date(2026, 6, 10), date(2026, 6, 12))
    # льготник тоже в отпуске в эти дни — не должен влиять на знаменатель/числитель
    approved_leave(benefits_user, date(2026, 6, 10), date(2026, 6, 12))
    db_session.flush()

    return {"division": division, "dept_a": dept_a, "dept_b": dept_b, "users_a": users_a}


def test_headcount_excludes_benefits_users(db_session, scenario):
    result = org_load_service.get_org_load(
        db_session, scenario["dept_a"].id, date(2026, 6, 10), date(2026, 6, 10)
    )
    assert result["headcount"] == 4  # 4, не 5 — льготник исключён


def test_load_fraction_and_band(db_session, scenario):
    result = org_load_service.get_org_load(
        db_session, scenario["dept_a"].id, date(2026, 6, 10), date(2026, 6, 10)
    )
    day = result["days"][0]
    assert day["on_leave"] == 1  # только обычный сотрудник, льготник не считается
    assert day["fraction"] == 0.25
    assert day["band"] == "green"


def test_day_outside_leave_range_is_zero(db_session, scenario):
    result = org_load_service.get_org_load(
        db_session, scenario["dept_a"].id, date(2026, 6, 13), date(2026, 6, 13)
    )
    assert result["days"][0]["on_leave"] == 0
    assert result["days"][0]["band"] == "green"


def test_rollup_to_division_sums_children(db_session, scenario):
    # 1 из 6 обычных сотрудников (4 в А + 2 в Б) в отпуске -> headcount юнита-родителя суммирует детей
    result = org_load_service.get_org_load(
        db_session, scenario["division"].id, date(2026, 6, 10), date(2026, 6, 10)
    )
    assert result["headcount"] == 6
    assert result["days"][0]["on_leave"] == 1


def test_high_load_band_red(db_session, scenario):
    # Ещё 2 из оставшихся 3 сотрудников отдела А уходят в те же дни -> 3/4 = 75% > 50% red
    leave_type = db_session.query(LeaveType).first()
    for u in scenario["users_a"][1:3]:
        db_session.add(
            LeaveRequest(
                user_id=u.id,
                leave_type_id=leave_type.id,
                date_from=date(2026, 6, 10),
                date_to=date(2026, 6, 10),
                status=APPROVED,
            )
        )
    db_session.flush()

    result = org_load_service.get_org_load(
        db_session, scenario["dept_a"].id, date(2026, 6, 10), date(2026, 6, 10)
    )
    assert result["days"][0]["fraction"] == 0.75
    assert result["days"][0]["band"] == "red"
