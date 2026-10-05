"""
Player access routes for secure game links and player sessions.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from auth.proxy import get_client_ip
from auth.player_access import (
    create_access_link,
    create_player_session,
    redeem_access_token,
    revoke_access_link,
    validate_player_session,
)
from auth.rbac import assert_resource_access, require_operator_with_bootstrap
from database import get_db_session, get_sessionmaker
from db_models import GameAccessLink, User
from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request, WebSocket, WebSocketDisconnect
from models import GameStateResponse, MessageResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from storage.db import db
# Connection manager is imported lazily to avoid circular imports
_manager = None

def get_manager():
    global _manager
    if _manager is None:
        from app import manager
        _manager = manager
    return _manager

router = APIRouter(tags=["Player Access"])


class CreateLinkRequest(BaseModel):
    policy: str = Field("LINK_ONLY", pattern=r"^(PUBLIC|LINK_ONLY|PASSWORD)$")
    password: Optional[str] = Field(None, min_length=4, max_length=128)
    expires_in_seconds: Optional[int] = Field(None, ge=60, le=2592000)
    max_uses: Optional[int] = Field(None, ge=1, le=1000)


class CreateLinkResponse(BaseModel):
    link_id: str
    access_token: str
    full_url: str
    policy: str
    expires_at: Optional[str]


class RedeemLinkRequest(BaseModel):
    token: str
    password: Optional[str] = None
    player_name: Optional[str] = Field(None, min_length=1, max_length=64)


class RedeemLinkResponse(BaseModel):
    player_session_token: str
    game_id: str
    game_state: Optional[dict]


class GameAccessPolicyRequest(BaseModel):
    policy: str = Field(..., pattern=r"^(PUBLIC|LINK_ONLY)$")


# ---------------------------------------------------------------------------
# Link management (operators/admins)
# ---------------------------------------------------------------------------


@router.post("/games/{game_id}/links", response_model=CreateLinkResponse)
async def create_link(
    game_id: str = Path(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$"),
    req: Optional[CreateLinkRequest] = None,
    current_user: Optional[User] = Depends(require_operator_with_bootstrap),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Create a new player access link for a game."""
    game = db.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if current_user:
        assert_resource_access(current_user, game.get("owner_id"))

    if req is None:
        req = CreateLinkRequest()

    if req.policy == "PASSWORD" and not req.password:
        raise HTTPException(status_code=400, detail="Password required for PASSWORD policy")

    expires_at = None
    if req.expires_in_seconds:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=req.expires_in_seconds)

    user_id = current_user.id if current_user else game.get("owner_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Cannot create link without owner")

    raw_token = await create_access_link(
        db=db_session,
        game_id=game_id,
        created_by=user_id,
        policy=req.policy,
        password=req.password,
        expires_at=expires_at,
        max_uses=req.max_uses,
    )

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    link = (await db_session.execute(
        select(GameAccessLink).where(GameAccessLink.token_hash == token_hash)
    )).scalar_one()

    return CreateLinkResponse(
        link_id=link.id,
        access_token=raw_token,
        full_url=f"/b/{raw_token}",
        policy=req.policy,
        expires_at=expires_at.isoformat() if expires_at else None,
    )


@router.get("/games/{game_id}/links")
async def list_links(
    game_id: str = Path(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$"),
    current_user: Optional[User] = Depends(require_operator_with_bootstrap),
    db_session: AsyncSession = Depends(get_db_session),
):
    """List all access links for a game."""
    game = db.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if current_user:
        assert_resource_access(current_user, game.get("owner_id"))

    stmt = select(GameAccessLink).where(GameAccessLink.game_id == game_id)
    links = (await db_session.execute(stmt)).scalars().all()

    return {
        "links": [
            {
                "id": link.id,
                "policy": link.policy,
                "created_at": link.created_at.isoformat() if link.created_at else None,
                "expires_at": link.expires_at.isoformat() if link.expires_at else None,
                "use_count": link.use_count,
                "max_uses": link.max_uses,
                "revoked": link.revoked_at is not None,
            }
            for link in links
        ]
    }


@router.delete("/games/{game_id}/links/{link_id}", response_model=MessageResponse)
async def revoke_link(
    game_id: str = Path(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\\-]+$"),
    link_id: str = Path(...),
    current_user: Optional[User] = Depends(require_operator_with_bootstrap),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Revoke an access link."""
    game = db.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if current_user:
        assert_resource_access(current_user, game.get("owner_id"))

    success = await revoke_access_link(db_session, link_id)
    if not success:
        raise HTTPException(status_code=404, detail="Link not found")

    return MessageResponse(message="Link revoked")


# ---------------------------------------------------------------------------
# Game access policy
# ---------------------------------------------------------------------------


@router.patch("/games/{game_id}/access-policy", response_model=MessageResponse)
async def update_access_policy(
    game_id: str = Path(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\\-]+$"),
    req: GameAccessPolicyRequest = None,
    current_user: Optional[User] = Depends(require_operator_with_bootstrap),
):
    """Update the access policy for a game."""
    if req is None:
        raise HTTPException(status_code=400, detail="Policy required")

    game = db.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if current_user:
        assert_resource_access(current_user, game.get("owner_id"))

    game["access_policy"] = req.policy
    return MessageResponse(message=f"Access policy updated to {req.policy}")


# ---------------------------------------------------------------------------
# Player link redemption (anonymous)
# ---------------------------------------------------------------------------


@router.post("/b/redeem", response_model=RedeemLinkResponse)
async def redeem_link(
    req: RedeemLinkRequest,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
):
    """Redeem an access link to join a game as a player."""
    if not req.token:
        raise HTTPException(status_code=400, detail="Access token required")

    client_ip = get_client_ip(request)

    result = await redeem_access_token(
        db=db_session,
        raw_token=req.token,
        password=req.password,
        ip_address=client_ip,
    )

    player_token = await create_player_session(
        db=db_session,
        game_id=result["game_id"],
        link_id=result["link_id"],
        player_name=req.player_name,
        ip_address=client_ip,
    )

    game = db.games.get(result["game_id"])
    game_state = None
    if game:
        game_state = {
            "game_id": result["game_id"],
            "drawn": list(game.get("drawn", [])),
            "mode": game.get("mode"),
            "stage": game.get("stage"),
            "status": game.get("status"),
        }

    return RedeemLinkResponse(
        player_session_token=player_token,
        game_id=result["game_id"],
        game_state=game_state,
    )


# ---------------------------------------------------------------------------
# Player-scoped game state access
# ---------------------------------------------------------------------------


@router.get("/b/{game_id}/state", response_model=GameStateResponse)
async def player_game_state(
    game_id: str,
    x_player_session: Optional[str] = Header(None, alias="X-Player-Session"),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Get game state. Requires player session for LINK_ONLY games."""
    game = db.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    access_policy = game.get("access_policy", "LINK_ONLY")
    if access_policy == "PUBLIC":
        return GameStateResponse(
            game_id=game_id,
            drawn=list(game.get("drawn", [])),
            mode=game.get("mode"),
            stage=game.get("stage"),
            status=game.get("status"),
        )

    if not x_player_session:
        raise HTTPException(status_code=401, detail="Player session required")

    session = await validate_player_session(db_session, x_player_session, game_id)
    if not session:
        raise HTTPException(status_code=403, detail="Invalid or expired player session")

    return GameStateResponse(
        game_id=game_id,
        drawn=list(game.get("drawn", [])),
        mode=game.get("mode"),
        stage=game.get("stage"),
        status=game.get("status"),
    )


@router.websocket("/ws/player/{game_id}")
async def player_websocket(websocket: WebSocket, game_id: str):
    """WebSocket endpoint for players."""
    player_token = websocket.query_params.get("token")

    if not player_token:
        await websocket.close(code=1008, reason="Player session required")
        return

    session_factory = get_sessionmaker()
    async with session_factory() as db_session:
        session = await validate_player_session(db_session, player_token, game_id)

    if not session:
        await websocket.close(code=1008, reason="Invalid player session")
        return

    manager = get_manager()
    connected = await manager.connect(game_id, websocket)
    if not connected:
        await websocket.close(code=1008, reason="Connection limit reached")
        return

    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        manager.disconnect(game_id, websocket)
