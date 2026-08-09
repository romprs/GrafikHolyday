from datetime import date

from app.models.restriction_settings import MIN_LEAVE_DURATION, PLANNING_YEAR, RestrictionSettings
from app.models.user import User
from app.services import restriction_settings_service


def test_update_changes_enabled_and_params(db_session):
    db_session.add(RestrictionSettings(key=MIN_LEAVE_DURATION, enabled=True, params={"min_days": 7}))
    actor = User(email="hr@settings.local", full_name="hr")
    db_session.add(actor)
    db_session.flush()

    updated = restriction_settings_service.update(
        db_session, actor, MIN_LEAVE_DURATION, enabled=False, params={"min_days": 3}
    )
    assert updated.enabled is False
    assert updated.params["min_days"] == 3
    assert updated.updated_by == actor.id


def test_planning_year_defaults_to_current_year_when_not_set(db_session):
    assert restriction_settings_service.get_planning_year(db_session) == date.today().year


def test_planning_year_reads_configured_value(db_session):
    db_session.add(RestrictionSettings(key=PLANNING_YEAR, enabled=True, params={"year": 2027}))
    db_session.flush()
    assert restriction_settings_service.get_planning_year(db_session) == 2027
