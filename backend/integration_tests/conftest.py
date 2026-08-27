import os


def pytest_configure():
    os.environ["CORS_ORIGINS"] = (
        "http://127.0.0.1:8000,"
        "http://test,"
        "http://localhost:3000,"
        "http://localhost:5173"
    )

    os.environ["CORS_ALLOW_CREDENTIALS"] = "true"
    os.environ["CARD_DB_PATH"] = ":memory:"
