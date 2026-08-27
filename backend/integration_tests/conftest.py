# backend/integration_test/conftest.py
import os


def pytest_configure():
    # Set default env vars for tests
    os.environ.setdefault(
        "CORS_ORIGINS",
        "http://127.0.0.1:8000,http://test,http://localhost:3000,http://localhost:5173",
    )
    os.environ.setdefault("CORS_ALLOW_CREDENTIALS", "true")
    # See backend/tests/conftest.py for why this is :memory: in tests.
    os.environ.setdefault("CARD_DB_PATH", ":memory:")
