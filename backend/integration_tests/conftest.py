# backend/integration_test/conftest.py
import os


def pytest_configure():
    # Set default env vars for tests
    os.environ.setdefault("CORS_ORIGINS", "http://127.0.0.1:8000, http://test")
    os.environ.setdefault("CORS_ALLOW_CREDENTIALS", "true")
