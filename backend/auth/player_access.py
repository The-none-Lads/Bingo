"""
Player access tokens and game link management.

Implements secure, shareable game links with:
- 256-bit CSPRNG tokens (secrets.token_urlsafe(32))
- One-way SHA-256 hash storage (raw tokens never persisted)
- Access policies: PUBLIC, LINK_ONLY, PASSWORD
- Argon2id for game passwords (never stored plaintext)
- Token expiration and revocation
- Rate limiting on redemption attempts
- Player sessions scoped to exactly one game
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from auth.rate_limit import auth_rate_limiter
from auth.security import hash_password, verify_password
from database import get_db_session
from db_models import GameAccessLink, PlayerSession
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession


def get_link_lifetime() -> int:
    """Get link lifetime in seconds from env (default: 7 days)."""
    import os
    return int(os.getenv("PLAYER_LINK_LIFETIME_SECONDS", str(7 * 24 * 60 * 60)))


def generate_access_token() -> str:
    """Generate a cryptographically random 256-bit URL-safe access token."""
    return secrets.token_urlsafe(32)


def hash_access_token(raw_token: str) -> str:
    """Compute one-way SHA-256 hash of raw access token for storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def create_access_link(
    db: AsyncSession,
    game_id: str,
    created_by: str,
    policy: str = "LINK_ONLY",
    password: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    max_uses: Optional[int] = None,
) -> str:
    """
    Create a new access link for a game.
    Returns the raw token (to be shared with the player).
    """
    raw_token = generate_access_token()
    token_hash = hash_access_token(raw_token)

    if not expires_at:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=get_link_lifetime())

    password_hash = None
    if password:
        password_hash = hash_password(password)

    link = GameAccessLink(
        game_id=game_id,
        created_by=created_by,
        token_hash=token_hash,
        policy=policy,
        password_hash=password_hash,
        expires_at=expires_at,
        max_uses=max_uses,
    )
    db.add(link)
    await db.commit()

    return raw_token


async def redeem_access_token(
    db: AsyncSession,
    raw_token: str,
    password: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> dict:
    """
    Redeem an access token and return game access info.
    Raises HTTPException on failure.
    """
    token_hash = hash_access_token(raw_token)
    now = datetime.now(timezone.utc)

    # Rate limiting on token redemption
    if ip_address:
        allowed, retry_after = await auth_rate_limiter.check_ip_limit(ip_address)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Too many attempts. Retry in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )
        await auth_rate_limiter.record_ip_attempt(ip_address)

    # Look up the link
    stmt = select(GameAccessLink).where(GameAccessLink.token_hash == token_hash)
    link = (await db.execute(stmt)).scalar_one_or_none()

    if not link:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    # Check expiration
    expires_at = link.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise HTTPException(status_code=410, detail="This link has expired")

    # Check revocation
    if link.revoked_at:
        raise HTTPException(status_code=410, detail="This link has been revoked")

    # Check max uses
    if link.max_uses is not None and link.use_count >= link.max_uses:
        raise HTTPException(status_code=410, detail="This link has reached its usage limit")

    # Check password if required
    if link.policy == "PASSWORD":
        if not password:
            raise HTTPException(status_code=401, detail="Password required")
        if not link.password_hash or not verify_password(password, link.password_hash):
            raise HTTPException(status_code=401, detail="Incorrect password")

    # Increment use count
    link.use_count += 1
    await db.commit()

    return {
        "game_id": link.game_id,
        "policy": link.policy,
        "link_id": link.id,
    }


async def create_player_session(
    db: AsyncSession,
    game_id: str,
    link_id: str,
    player_name: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> str:
    """
    Create a short-lived player session scoped to exactly one game.
    Returns the raw session token.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_access_token(raw_token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=get_link_lifetime())

    session = PlayerSession(
        game_id=game_id,
        link_id=link_id,
        session_token_hash=token_hash,
        player_name=player_name,
        ip_address=ip_address,
        expires_at=expires_at,
    )
    db.add(session)
    await db.commit()

    return raw_token


async def validate_player_session(
    db: AsyncSession,
    raw_token: str,
    game_id: str,
) -> Optional[PlayerSession]:
    """
    Validate a player session token for a specific game.
    Returns the session if valid, None otherwise.
    """
    token_hash = hash_access_token(raw_token)
    now = datetime.now(timezone.utc)

    stmt = (
        select(PlayerSession)
        .where(
            PlayerSession.session_token_hash == token_hash,
            PlayerSession.game_id == game_id,
        )
    )
    session = (await db.execute(stmt)).scalar_one_or_none()

    if not session:
        return None

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < now:
        # Session expired, clean it up
        await db.delete(session)
        await db.commit()
        return None

    if session.revoked_at:
        return None

    return session


async def revoke_access_link(db: AsyncSession, link_id: str) -> bool:
    """Revoke an access link (soft delete)."""
    stmt = select(GameAccessLink).where(GameAccessLink.id == link_id)
    link = (await db.execute(stmt)).scalar_one_or_none()
    if not link:
        return False

    link.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return True


async def revoke_player_session(db: AsyncSession, raw_token: str) -> bool:
    """Revoke a player session."""
    token_hash = hash_access_token(raw_token)
    stmt = select(PlayerSession).where(PlayerSession.session_token_hash == token_hash)
    session = (await db.execute(stmt)).scalar_one_or_none()
    if not session:
        return False

    session.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return True


async def cleanup_expired_sessions(db: AsyncSession) -> int:
    """Remove expired player sessions."""
    now = datetime.now(timezone.utc)
    stmt = delete(PlayerSession).where(PlayerSession.expires_at < now)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0
