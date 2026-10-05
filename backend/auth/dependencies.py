import os
import secrets
from typing import Optional

from auth.proxy import get_client_ip
from auth.session import SESSION_COOKIE_NAME, get_session_user
from database import get_db_session
from db_models import User
from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_current_user(
    request: Request,
    session_cookie: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db_session),
) -> Optional[User]:
    """
    Extract and validate the current authenticated user from session cookie or Bearer header.
    Returns User if valid and active; None otherwise.
    """
    token = session_cookie

    # Fallback to Authorization: Bearer <token> if cookie is not present
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            # Avoid matching ADMIN_API_KEY as a session token
            admin_key = os.getenv("ADMIN_API_KEY") or os.getenv("ADMIN_SECRET")
            if not admin_key or not secrets.compare_digest(parts[1], admin_key):
                token = parts[1]

    if not token:
        return None

    return await get_session_user(db, token)


async def require_authenticated_user(
    user: Optional[User] = Depends(get_current_user),
) -> User:
    """Dependency that enforces a valid, active authenticated session."""
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )
    return user


async def require_admin(
    user: User = Depends(require_authenticated_user),
) -> User:
    """Dependency that enforces ADMIN role."""
    if user.role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Administrator privileges required",
        )
    return user


async def verify_admin_flexible(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    authorization: Optional[str] = Header(None),
    user: Optional[User] = Depends(get_current_user),
) -> bool:
    """
    Unified admin verification:
    1. If user is logged in with role == "ADMIN", grant access.
    2. If ADMIN_API_KEY / ADMIN_SECRET is configured, check X-Admin-Key or Bearer token.
    3. If neither ADMIN_API_KEY nor any users exist, allow open access for dev/standalone.
    """
    # 1. Check logged-in user role
    if user and user.role == "ADMIN":
        return True

    # 2. Check legacy admin key
    admin_key = os.getenv("ADMIN_API_KEY") or os.getenv("ADMIN_SECRET")
    if admin_key:
        if x_admin_key and secrets.compare_digest(x_admin_key, admin_key):
            return True
        if authorization:
            parts = authorization.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                if secrets.compare_digest(parts[1], admin_key):
                    return True
        # If admin key is configured and was not matched / user is not admin
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Admin authentication required",
        )

    # 3. If no admin key is configured in env, allow open access
    return True
