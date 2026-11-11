"""
Admin API routes for user management, session monitoring, and system health.

These endpoints are restricted to ADMIN role.
"""

from datetime import datetime, timezone
from typing import Optional

from auth.rbac import require_admin
from database import get_db_session
from db_models import User, UserAuthMethod, UserSession
from fastapi import APIRouter, Depends, HTTPException, Query
from models import (
    GameSettingsRequest,
    GameSettingsResponse,
    MessageResponse,
    UserAdminResponse,
    UserQuotaInfo,
    UserUpdateRequest,
)
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from storage.db import db

router = APIRouter(prefix="/admin", tags=["Administration"])


def format_user_admin_response(user: User) -> UserAdminResponse:
    """Format a User for admin response."""
    now = datetime.now(timezone.utc)
    active_sessions = []
    for s in user.sessions:
        exp = s.expires_at
        if exp is not None:
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp > now:
                active_sessions.append(s)
    return UserAdminResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else None,
        updated_at=user.updated_at.isoformat() if user.updated_at else None,
        auth_providers=[am.auth_provider for am in user.auth_methods],
        session_count=len(active_sessions),
    )


@router.get("/users", response_model=list[UserAdminResponse], summary="List all users")
async def list_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    role_filter: Optional[str] = None,
    active_only: bool = False,
    current_admin: User = Depends(require_admin),
    db_session: AsyncSession = Depends(get_db_session),
):
    """List all users with pagination and optional filtering."""
    stmt = select(User).offset(offset).limit(limit)
    if role_filter:
        stmt = stmt.where(User.role == role_filter.upper())
    if active_only:
        stmt = stmt.where(User.is_active == True)
    result = await db_session.execute(stmt)
    users = result.scalars().all()
    return [format_user_admin_response(u) for u in users]


@router.get("/users/{user_id}", response_model=UserAdminResponse, summary="Get user by ID")
async def get_user(
    user_id: str,
    current_admin: User = Depends(require_admin),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Get a specific user's details."""
    stmt = select(User).where(User.id == user_id)
    user = (await db_session.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return format_user_admin_response(user)


@router.patch("/users/{user_id}", response_model=UserAdminResponse, summary="Update user role/status")
async def update_user(
    user_id: str,
    req: UserUpdateRequest,
    current_admin: User = Depends(require_admin),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Update a user's role or active status. Cannot disable the last ADMIN."""
    user = (await db_session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_admin.id and (
        req.role is not None or req.is_active is not None
    ):
        raise HTTPException(status_code=400, detail="Cannot modify your own account")

    # Prevent disabling the last active ADMIN
    if req.is_active is False and user.role == "ADMIN":
        admin_count = (
            await db_session.execute(
                select(func.count(User.id)).where(
                    User.role == "ADMIN", User.is_active == True
                )
            )
        ).scalar_one()
        if admin_count <= 1:
            raise HTTPException(
                status_code=409,
                detail="Cannot disable the last active administrator account",
            )

    # Prevent demoting the last ADMIN
    if req.role and req.role != "ADMIN" and user.role == "ADMIN":
        admin_count = (
            await db_session.execute(
                select(func.count(User.id)).where(
                    User.role == "ADMIN", User.is_active == True
                )
            )
        ).scalar_one()
        if admin_count <= 1:
            raise HTTPException(
                status_code=409,
                detail="Cannot demote the last active administrator",
            )

    if req.role:
        user.role = req.role
    if req.is_active is not None:
        user.is_active = req.is_active

    await db_session.commit()
    await db_session.refresh(user)
    return format_user_admin_response(user)


@router.delete(
    "/users/{user_id}",
    response_model=MessageResponse,
    summary="Delete a user account (admin)",
)
async def admin_delete_user(
    user_id: str,
    current_admin: User = Depends(require_admin),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Delete a user account. Cannot delete self or last ADMIN."""
    user = (await db_session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account.")

    if user.role == "ADMIN":
        admin_count = (
            await db_session.execute(
                select(func.count(User.id)).where(
                    User.role == "ADMIN", User.is_active == True
                )
            )
        ).scalar_one()
        if admin_count <= 1:
            raise HTTPException(status_code=409, detail="Cannot delete the last active administrator")

    from auth.session import revoke_all_user_sessions
    await revoke_all_user_sessions(db_session, user.id)
    await db_session.delete(user)
    await db_session.commit()
    return MessageResponse(message=f"User {user.username} deleted.")


@router.post(
    "/users/{user_id}/reset-password",
    response_model=MessageResponse,
    summary="Force password reset (admin)",
)
async def admin_reset_password(
    user_id: str,
    current_admin: User = Depends(require_admin),
    db_session: AsyncSession = Depends(get_db_session),
):
    """
    Mark a user's local password as requiring reset on next login.
    The user will be forced to set a new password on next login.
    """
    user = (await db_session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Find local auth method
    auth_method = None
    for am in user.auth_methods:
        if am.auth_provider == "local":
            auth_method = am
            break

    if not auth_method:
        raise HTTPException(
            status_code=400,
            detail="User has no local authentication method",
        )

    # Revoke all sessions for this user (force re-login)
    result = await db_session.execute(
        delete(UserSession).where(UserSession.user_id == user_id)
    )
    await db_session.commit()

    return MessageResponse(
        message="User sessions revoked. Password reset will be required on next login."
    )


@router.get(
    "/users/{user_id}/sessions",
    summary="List active sessions for a user",
)
async def list_user_sessions(
    user_id: str,
    current_admin: User = Depends(require_admin),
    db_session: AsyncSession = Depends(get_db_session),
):
    """List all sessions for a specific user."""
    user = (await db_session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(timezone.utc)
    sessions = []
    for s in user.sessions:
        expires_at = s.expires_at.replace(tzinfo=timezone.utc) if s.expires_at.tzinfo is None else s.expires_at
        sessions.append({
            "id": s.id,
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            "last_active_at": s.last_active_at.isoformat() if s.last_active_at else None,
            "is_expired": expires_at < now,
        })
    return {"count": len(sessions), "sessions": sessions}


@router.delete(
    "/users/{user_id}/sessions",
    response_model=MessageResponse,
    summary="Revoke all sessions for a user",
)
async def revoke_user_sessions(
    user_id: str,
    current_admin: User = Depends(require_admin),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Revoke all active sessions for a user (force logout)."""
    from auth.session import revoke_all_user_sessions
    count = await revoke_all_user_sessions(db_session, user_id)
    return MessageResponse(message=f"Revoked {count} session(s)")


@router.post(
    "/sessions/global-logout",
    response_model=MessageResponse,
    summary="Force logout all users",
)
async def global_logout(
    current_admin: User = Depends(require_admin),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Revoke ALL active sessions system-wide (except current admin)."""
    # Delete all sessions except the current admin's
    result = await db_session.execute(
        select(UserSession).where(UserSession.user_id != current_admin.id)
    )
    sessions = result.scalars().all()
    for s in sessions:
        await db_session.delete(s)
    await db_session.commit()
    return MessageResponse(message=f"Revoked {len(sessions)} session(s) system-wide")


@router.get(
    "/users/{user_id}/quotas",
    response_model=UserQuotaInfo,
    summary="Get user quota usage",
)
async def get_user_quotas(
    user_id: str,
    current_admin: User = Depends(require_admin),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Check a user's resource usage against their quotas."""
    # Count active games owned by this user
    active_games = sum(
        1 for g in db.games.values()
        if g.get("owner_id") == user_id and g.get("status") == "active"
    )

    # Count persistent cards owned by this user
    persistent_cards = sum(
        1 for pid, card in db.cards.items()
        if card.get("owner_id") == user_id and db.cards.is_persistent(pid)
    )

    return UserQuotaInfo(
        active_games=active_games,
        max_games=db.max_games,
        persistent_cards=persistent_cards,
        max_persistent_cards=db.cards.max_persistent_cards,
    )


@router.get("/games", summary="List active games and admin settings")
async def list_active_games(
    current_admin: User = Depends(require_admin),
):
    """List currently active games alongside game-management settings."""
    active_games = []
    for game_id, game in sorted(db.games.items()):
        if game.get("status") != "active":
            continue
        last_activity = game.get("last_activity_at")
        try:
            if last_activity:
                last_activity_dt = datetime.fromisoformat(last_activity)
                if last_activity_dt.tzinfo is None:
                    last_activity_dt = last_activity_dt.replace(tzinfo=timezone.utc)
            else:
                last_activity_dt = None
        except ValueError:
            last_activity_dt = None
        active_games.append(
            {
                "game_id": game_id,
                "mode": game.get("mode"),
                "status": game.get("status"),
                "stage": game.get("stage"),
                "drawn_count": len(game.get("drawn", [])),
                "last_activity_at": last_activity_dt.isoformat() if last_activity_dt else None,
                "owner_id": game.get("owner_id"),
            }
        )

    return {
        "active_games": active_games,
        "max_concurrent_games": db.max_concurrent_games,
        "inactivity_timeout_minutes": db.inactivity_timeout_minutes,
        "active_game_count": len(active_games),
        "available_capacity": max(0, db.max_concurrent_games - len(active_games)),
    }


@router.get("/settings", response_model=GameSettingsResponse, summary="Get game settings")
async def get_game_settings(
    current_admin: User = Depends(require_admin),
):
    """Return the current game-management settings."""
    active_games = db.count_active_games()
    return GameSettingsResponse(
        max_concurrent_games=db.max_concurrent_games,
        inactivity_timeout_minutes=db.inactivity_timeout_minutes,
        active_games=active_games,
        available_capacity=max(0, db.max_concurrent_games - active_games),
    )


@router.patch("/settings", response_model=GameSettingsResponse, summary="Update game settings")
async def update_game_settings(
    req: GameSettingsRequest,
    current_admin: User = Depends(require_admin),
):
    """Persist the instance-wide game-management settings."""
    if req.max_concurrent_games < 1 or req.max_concurrent_games > 200:
        raise HTTPException(status_code=400, detail="max_concurrent_games must be between 1 and 200")
    if req.inactivity_timeout_minutes < 30 or req.inactivity_timeout_minutes > 60:
        raise HTTPException(status_code=400, detail="inactivity_timeout_minutes must be between 30 and 60")

    db.max_concurrent_games = req.max_concurrent_games
    db.inactivity_timeout_minutes = req.inactivity_timeout_minutes
    db.save_settings()
    active_games = db.count_active_games()
    return GameSettingsResponse(
        max_concurrent_games=db.max_concurrent_games,
        inactivity_timeout_minutes=db.inactivity_timeout_minutes,
        active_games=active_games,
        available_capacity=max(0, db.max_concurrent_games - active_games),
    )


@router.post("/games/{game_id}/stop", response_model=MessageResponse, summary="Stop an active game")
async def stop_game(
    game_id: str,
    current_admin: User = Depends(require_admin),
):
    """Stop a game and release the active-game slot."""
    game = db.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.get("status") in {"stopped", "expired", "finished", "completed"}:
        return MessageResponse(message=f"Game {game_id} is already closed")

    db.mark_game_terminal(game_id, status="stopped", reason="manual_stop", now=datetime.now(timezone.utc))
    from app import broadcast_game_state
    await broadcast_game_state(game_id)
    return MessageResponse(message=f"Game {game_id} stopped")


@router.get("/system/health", summary="System health overview")
async def system_health(
    current_admin: User = Depends(require_admin),
    db_session: AsyncSession = Depends(get_db_session),
):
    """System resource overview for admin dashboard."""
    now = datetime.now(timezone.utc)

    # User stats
    total_users = (await db_session.execute(select(func.count(User.id)))).scalar_one()
    active_users = (
        await db_session.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
    ).scalar_one()

    # Session stats
    total_sessions = (
        await db_session.execute(select(func.count(UserSession.id)))
    ).scalar_one()
    active_sessions = (
        await db_session.execute(
            select(func.count(UserSession.id)).where(
                UserSession.expires_at > now
            )
        )
    ).scalar_one()

    active_game_count = db.count_active_games()
    return {
        "users": {
            "total": total_users,
            "active": active_users,
        },
        "games": {
            "active": active_game_count,
            "total": len(db.games),
            "max": db.max_concurrent_games,
            "available_capacity": max(0, db.max_concurrent_games - active_game_count),
        },
        "settings": {
            "max_concurrent_games": db.max_concurrent_games,
            "inactivity_timeout_minutes": db.inactivity_timeout_minutes,
        },
        "cards": {
            "ephemeral": len(db.cards._memory) if hasattr(db.cards, '_memory') else 0,
            "persistent": db.cards._persistent_count() if hasattr(db.cards, '_persistent_count') else 0,
        },
        "sessions": {
            "total": total_sessions,
            "active": active_sessions,
        },
    }
