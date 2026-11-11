import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from db_models import User, UserSession
from fastapi import Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

# Cookie & Session Configuration
SESSION_COOKIE_NAME = "bingo_session"
DEFAULT_SESSION_LIFETIME_SECONDS = 7 * 24 * 60 * 60  # 7 days


def get_session_lifetime() -> int:
    try:
        return int(os.getenv("SESSION_LIFETIME_SECONDS", str(DEFAULT_SESSION_LIFETIME_SECONDS)))
    except ValueError:
        return DEFAULT_SESSION_LIFETIME_SECONDS


def is_cookie_secure() -> bool:
    """Determine whether the session cookie should require Secure (HTTPS)."""
    env_override = os.getenv("SESSION_COOKIE_SECURE")
    if env_override is not None:
        return env_override.lower() in ("true", "1", "yes", "on")
    env = os.getenv("ENVIRONMENT", "development").lower()
    return env == "production"


def hash_session_token(raw_token: str) -> str:
    """Compute one-way SHA-256 hash of raw session token for database storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_session_token() -> str:
    """Generate a cryptographically random 256-bit URL-safe session token."""
    return secrets.token_urlsafe(32)


async def create_session(
    db: AsyncSession,
    user_id: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> str:
    """Create a new server-side session and return the raw session token."""
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=get_session_lifetime())

    session = UserSession(
        user_id=user_id,
        session_token_hash=token_hash,
        ip_address=ip_address,
        user_agent=user_agent[:512] if user_agent else None,
        expires_at=expires_at,
        created_at=now,
        last_active_at=now,
    )
    db.add(session)
    await db.commit()
    return raw_token


async def get_session_user(db: AsyncSession, raw_token: str) -> Optional[User]:
    """
    Validate a raw session token against the database.
    Returns the User if valid, active, and unexpired; None otherwise.
    """
    if not raw_token or not isinstance(raw_token, str):
        return None

    token_hash = hash_session_token(raw_token)
    now = datetime.now(timezone.utc)

    stmt = (
        select(UserSession, User)
        .join(User, UserSession.user_id == User.id)
        .where(UserSession.session_token_hash == token_hash)
    )
    result = await db.execute(stmt)
    row = result.first()

    if not row:
        return None

    session, user = row

    # Ensure timezone comparison compatibility
    session_exp = session.expires_at
    if session_exp.tzinfo is None:
        session_exp = session_exp.replace(tzinfo=timezone.utc)

    if session_exp < now:
        # Session expired: remove it
        await db.delete(session)
        await db.commit()
        return None

    if not user.is_active:
        # User account is disabled: reject access immediately
        return None

    # Update last_active_at
    session.last_active_at = now
    await db.commit()

    return user


async def revoke_session(db: AsyncSession, raw_token: str) -> bool:
    """Revoke a single session by its raw token."""
    if not raw_token:
        return False
    token_hash = hash_session_token(raw_token)
    stmt = delete(UserSession).where(UserSession.session_token_hash == token_hash)
    result = await db.execute(stmt)
    await db.commit()
    return bool(result.rowcount and result.rowcount > 0)


async def revoke_all_user_sessions(db: AsyncSession, user_id: str) -> int:
    """Revoke all active sessions for a user (e.g. on password change or logout-all)."""
    stmt = delete(UserSession).where(UserSession.user_id == user_id)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0


async def cleanup_expired_sessions(db: AsyncSession) -> int:
    """Purge all expired sessions from the database."""
    now = datetime.now(timezone.utc)
    stmt = delete(UserSession).where(UserSession.expires_at < now)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0


def set_session_cookie(response: Response, raw_token: str) -> None:
    """Set the HttpOnly session cookie on the FastAPI response."""
    lifetime = get_session_lifetime()
    secure = is_cookie_secure()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=lifetime,
        expires=lifetime,
        path="/",
        httponly=True,
        secure=secure,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    """Clear the session cookie on logout."""
    secure = is_cookie_secure()
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=secure,
        samesite="lax",
    )
