import os
import tempfile
from uuid import uuid4

# The integration suite must never drop tables from the developer's hospital.db.
TEST_DB_PATH = os.path.join(tempfile.gettempdir(), f"hms-commission-tests-{uuid4().hex}.db")
os.environ["HMS_DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

import pytest


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database():
    from app.core.database import Base, engine
    from app.seed import seed_database

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_database()
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    try:
        os.remove(TEST_DB_PATH)
    except FileNotFoundError:
        pass
