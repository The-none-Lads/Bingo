# backend/tests/conftest.py
import os

# Set env vars BEFORE any other imports that may use the database
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["CORS_ALLOW_CREDENTIALS"] = "true"
os.environ["ENVIRONMENT"] = "development"
os.environ["ALLOW_REGISTRATION"] = "true"
os.environ["PYTHON_DOTENV_DISABLED"] = "true"
os.environ.pop("ADMIN_API_KEY", None)
os.environ.pop("ADMIN_SECRET", None)
os.environ.pop("INITIAL_ADMIN_TOKEN", None)
os.environ["CARD_DB_PATH"] = ":memory:"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
