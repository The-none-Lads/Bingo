# backend/tests/conftest.py
import os


def pytest_configure():
    # Set default env vars for tests
    os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
    os.environ.setdefault("CORS_ALLOW_CREDENTIALS", "true")
    # ":memory:" keeps the card store fully in-process and per-instance,
    # so tests never touch disk or pollute/read a real deployment's
    # persisted card file (backend/data/cards.db by default).
    os.environ.setdefault("CARD_DB_PATH", ":memory:")
