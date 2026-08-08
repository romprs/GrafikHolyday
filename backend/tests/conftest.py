import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base

# SQLite in-memory: достаточно для unit-тестов сервисного слоя (без Postgres-специфичных
# фич вроде generate_series/recursive CTE, которые проверяются интеграционными тестами
# на реальном Postgres в последующих фазах).
_ENGINE = create_engine("sqlite:///:memory:")


@pytest.fixture()
def db_session():
    Base.metadata.create_all(_ENGINE)
    session = Session(bind=_ENGINE)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(_ENGINE)
