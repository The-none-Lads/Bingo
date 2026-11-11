# conftest.py
"""
Root-level conftest.py for pytest.
Sets environment variables before any imports that use the database.
"""
import os
import tempfile

# Set env vars BEFORE any other imports that may use the database
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["CORS_ALLOW_CREDENTIALS"] = "true"

# Use a temp file for the test database (not :memory:)
# This ensures the database persists across connections
_test_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["CARD_DB_PATH"] = _test_db_file.name
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_db_file.name}"


def pytest_configure(config):
    """Called after command line options have been parsed."""
    # Create tables synchronously before any tests
    from sqlalchemy import create_engine
    from database import Base
    
    db_url = os.environ["DATABASE_URL"].replace("sqlite+aiosqlite", "sqlite")
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    engine.dispose()


def pytest_unconfigure(config):
    """Called after all tests have finished."""
    # Clean up temp database file
    try:
        os.unlink(_test_db_file.name)
    except OSError:
        pass
