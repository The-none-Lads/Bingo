# backend/tests/conftest.py
import os

# Set env vars BEFORE any other imports that may use the database
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["CORS_ALLOW_CREDENTIALS"] = "true"
os.environ["CARD_DB_PATH"] = ":memory:"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
