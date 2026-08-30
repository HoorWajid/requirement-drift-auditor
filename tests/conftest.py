"""
Test fixtures. Sets env vars BEFORE app.main is imported by any test module,
and points the DB at an isolated test database so tests never touch app.db
(test data polluting the dev DB would cause later manual testing to show
stale/incorrect results).
"""
import os
os.environ.setdefault("JWT_SECRET_KEY", "67bnPnzg6bo3iO8eotRHNyB_3qgQb5gdBlNfeMC79jg")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_app.db")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:8501")
os.environ.setdefault("CHATBOT_ENGINE", "rule_based")
os.environ.setdefault("COOKIE_SECURE", "false")

import pytest
from app.database import Base, engine


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("test_app.db"):
        os.remove("test_app.db")