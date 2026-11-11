import os


def pytest_configure():
    os.environ["PYTHON_DOTENV_DISABLED"] = "true"
    os.environ["ENVIRONMENT"] = "development"
    os.environ["ALLOW_REGISTRATION"] = "true"
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ.pop("ADMIN_API_KEY", None)
    os.environ.pop("ADMIN_SECRET", None)
    os.environ.pop("INITIAL_ADMIN_TOKEN", None)
    os.environ["CORS_ORIGINS"] = (
        "http://127.0.0.1:8000,"
        "http://test,"
        "http://localhost:3000,"
        "http://localhost:5173"
    )

    os.environ["CORS_ALLOW_CREDENTIALS"] = "true"
    os.environ["CARD_DB_PATH"] = ":memory:"
