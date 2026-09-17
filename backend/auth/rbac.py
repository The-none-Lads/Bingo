"""
RBAC (Role-Based Access Control) and resource ownership enforcement.

Roles:
- ADMIN: Full system visibility and management.
- OPERATOR: Can create, run, and manage only their own games and card batches.
- USER: Read-only access to public endpoints (game state, validation).

Resource ownership:
- Games and cards are bound to owner_id (the creating user).
- ADMIN can access all resources.
- OPERATOR can only access their own resources.
- Legacy resources with owner_id = NULL are treated as system-owned (ADMIN only).
"""

from typing import Optional

from auth.dependencies import get_current_user, require_authenticated_user
from db_models import User
from fastapi import Depends, HTTPException

# Role hierarchy: higher number = more privileges
ROLE_HIERARCHY = {
    "USER": 0,
    "OPERATOR": 1,
    "ADMIN": 2,
}


def role_level(role: str) -> int:
    """Get the privilege level for a role string."""
    return ROLE_HIERARCHY.get(role.upper(), 0)


def has_role(user: User, required_role: str) -> bool:
    """Check if user's role meets or exceeds the required role."""
    return role_level(user.role) >= role_level(required_role)


class RBACError(HTTPException):
    """Raised when RBAC check fails."""

    def __init__(self, detail: str = "Forbidden"):
        super().__init__(status_code=403, detail=detail)


# ---------------------------------------------------------------------------
# Dependencies for protecting endpoints
# ---------------------------------------------------------------------------


async def require_operator_with_bootstrap(
    user: Optional[User] = Depends(get_current_user),
) -> Optional[User]:
    """
    Require OPERATOR or ADMIN role, but allow open access when no users exist
    (bootstrap mode for initial setup).
    """
    from database import get_db_session
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession

    db_session: AsyncSession = await anext(get_db_session())
    result = await db_session.execute(select(func.count(User.id)))
    total_users = result.scalar_one()

    if total_users == 0:
        return None

    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    if not has_role(user, "OPERATOR"):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Operator or Administrator privileges required",
        )

    return user


async def require_admin(
    user: User = Depends(require_authenticated_user),
) -> User:
    """Require ADMIN role."""
    if not has_role(user, "ADMIN"):
        raise RBACError("Forbidden: Administrator privileges required")
    return user


# ---------------------------------------------------------------------------
# Resource ownership checks
# ---------------------------------------------------------------------------


def check_resource_access(user: User, owner_id: Optional[str]) -> bool:
    """
    Check if a user can access a resource based on ownership.

    - ADMIN can access any resource.
    - OPERATOR can access their own resources and system-owned (NULL) resources.
    - USER cannot access admin/operator resources.
    """
    if role_level(user.role) >= ROLE_HIERARCHY["ADMIN"]:
        return True

    if owner_id is None:
        # System-owned resource: only ADMIN can access
        return False

    return owner_id == user.id


def assert_resource_access(user: User, owner_id: Optional[str]) -> None:
    """Raise RBACError if user cannot access the resource."""
    if not check_resource_access(user, owner_id):
        raise RBACError(
            "Forbidden: You do not have permission to access this resource"
        )


# ---------------------------------------------------------------------------
# Unified admin verification (replaces verify_admin_flexible for game/card routes)
# ---------------------------------------------------------------------------


async def verify_admin_or_operator(
    user: Optional[User] = Depends(get_current_user),
) -> User:
    """
    Verify the user is authenticated and has OPERATOR or ADMIN role.

    This replaces the legacy verify_admin_flexible for game/card endpoints.
    When no users exist yet (fresh install), allows open access for bootstrap.
    """
    from database import get_db_session
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession

    # Check if any users exist (bootstrap mode)
    db: AsyncSession = await anext(get_db_session())
    result = await db.execute(select(func.count(User.id)))
    total_users = result.scalar_one()

    if total_users == 0:
        # No users yet: allow open access for initial setup
        # This maintains backward compatibility with standalone/dev mode
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please register an account.",
        )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    if not has_role(user, "OPERATOR"):
        raise RBACError(
            "Forbidden: Operator or Administrator privileges required"
        )

    return user


async def verify_game_owner_or_admin(
    game_id: str,
    user: User = Depends(require_authenticated_user),
) -> User:
    """
    Verify the user owns the specified game or is ADMIN.
    Used as a dependency for game-specific routes.
    """
    from storage.db import db

    game = db.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    owner_id = game.get("owner_id")
    assert_resource_access(user, owner_id)
    return user
