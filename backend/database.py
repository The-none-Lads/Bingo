import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


def get_database_url() -> str:
    """
    Resolve the database URL.
    - If DATABASE_URL is set, use it (converting sqlite:// to sqlite+aiosqlite:// if needed).
    - Otherwise, use CARD_DB_PATH (default: data/cards.db).
    - If CARD_DB_PATH is ':memory:', use in-memory SQLite.
    """
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite+aiosqlite:///"):
            return db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        if db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
            return db_url.replace("postgresql://", "postgresql+asyncpg://")
        return db_url

    card_db_path = os.getenv("CARD_DB_PATH", "data/cards.db")
    if card_db_path == ":memory:":
        return "sqlite+aiosqlite:///:memory:"

    # Ensure directory exists for file-based SQLite
    dirname = os.path.dirname(card_db_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

    # Normalize path for SQLite URI
    normalized_path = os.path.abspath(card_db_path).replace("\\", "/")
    return f"sqlite+aiosqlite:///{normalized_path}"


class Base(DeclarativeBase):
    pass


# Global engine and sessionmaker
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = get_database_url()
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_async_engine(
            url,
            echo=False,
            connect_args=connect_args,
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _sessionmaker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an AsyncSession."""
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables directly (for SQLite dev/testing/standalone)."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose of the engine connection pool."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
