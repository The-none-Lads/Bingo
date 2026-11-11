import os


def is_production() -> bool:
    return os.getenv("ENVIRONMENT", "development").strip().lower() == "production"


def get_admin_api_key() -> str | None:
    return os.getenv("ADMIN_API_KEY") or os.getenv("ADMIN_SECRET")


def allow_open_bootstrap() -> bool:
    return not is_production() and not get_admin_api_key()
