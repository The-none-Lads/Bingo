# backend/tests/conftest.py
import os

def pytest_configure():
    # Set default env vars for tests
    os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
    os.environ.setdefault("CORS_ALLOW_CREDENTIALS", "true")
