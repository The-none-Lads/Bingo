import asyncio
import logging
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from auth.config import allow_open_bootstrap, get_admin_api_key, is_production
from auth.dependencies import get_current_user, verify_admin_flexible
from auth.headers import SecurityHeadersMiddleware
from auth.rbac import assert_resource_access, has_role, require_admin, require_operator_with_bootstrap
from auth.session import SESSION_COOKIE_NAME, get_session_user
from database import close_db, get_db_session, get_sessionmaker, init_db
from db_models import User
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Path,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from logic.cards import generate_75_ball_card, serialize_card, short_id
from logic.draws import DrawEngine
from logic.validate import validate_card
from models import (
    CardBatchRequest,
    CardResponse,
    CreateGameRequest,
    GameSettingsRequest,
    GameSettingsResponse,
    GameStateResponse,
    ValidateRequest,
    ValidateResponse,
)
from routes.auth import router as auth_router
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from storage.db import PersistentStorageFullError, PersistentStorageUnavailableError, db

load_dotenv()
logger = logging.getLogger(__name__)


def get_bool_env(key: str, default: bool = True) -> bool:
    """Get boolean from environment variable."""
    value = os.getenv(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


def is_docs_enabled() -> bool:
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env == "production":
        return get_bool_env("ENABLE_DOCS", False)
    return get_bool_env("ENABLE_DOCS", True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing database initialization and cleanup."""
    await init_db()
    app.state.expiration_task = asyncio.create_task(_expire_inactive_games_loop())
    try:
        yield
    finally:
        app.state.expiration_task.cancel()
        await close_db()


app = FastAPI(
    title="Bingo Game API",
    docs_url="/docs" if is_docs_enabled() else None,
    redoc_url="/redoc" if is_docs_enabled() else None,
    openapi_url="/openapi.json" if is_docs_enabled() else None,
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
async def health_check(
    db_session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    await db_session.execute(select(1))
    return {"status": "ok"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_game_state(game_id: str) -> dict:
    game = db.games.get(game_id)
    if not game:
        return {}
    return {
        "game_id": game_id,
        "drawn": list(game["drawn"]),
        "mode": game["mode"],
        "stage": game["stage"],
        "status": game["status"],
        "access_policy": game.get("access_policy", "LINK_ONLY"),
        "last_activity_at": game.get("last_activity_at"),
    }


async def _expire_inactive_games(now: Optional[datetime] = None) -> list[str]:
    expired = db.expire_inactive_games(now=now or _utc_now())
    for game_id in expired:
        await manager.close_game_connections(game_id, "Game expired from inactivity")
    return expired


async def _expire_inactive_games_loop() -> None:
    while True:
        try:
            await _expire_inactive_games()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive loop safety
            logger.exception("Inactive game expiry check failed: %s", exc)
        await asyncio.sleep(30)


# Configuration from environment variables
def get_cors_origins() -> List[str]:
    """Use localhost defaults only outside production."""
    origins_str = os.getenv("CORS_ORIGINS")
    if origins_str is None or not origins_str.strip():
        if is_production():
            raise RuntimeError("CORS_ORIGINS must be explicitly configured in production")
        return [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://localhost:80",
            "http://localhost:8000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:80",
            "http://127.0.0.1:8000",
        ]

    origins = [origin.strip() for origin in origins_str.split(",") if origin.strip()]
    if not origins:
        raise RuntimeError("CORS_ORIGINS must contain at least one origin")
    if "*" in origins:
        if is_production():
            raise RuntimeError("Wildcard CORS origins are not allowed in production")
        return ["*"]

    return origins


cors_origins = get_cors_origins()
allow_credentials = get_bool_env("CORS_ALLOW_CREDENTIALS", True)
# Enforce W3C/Fetch standard: wildcard origin cannot be used with credentials
if "*" in cors_origins:
    allow_credentials = False

# Security & CORS Middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth_router)
from routes.admin import router as admin_router

app.include_router(admin_router)
from routes.player_access import router as player_router

app.include_router(player_router)
from routes.oidc import router as oidc_router

app.include_router(oidc_router)


# -------------------------
# Authentication / Authorization
# -------------------------


async def verify_admin(
    is_admin: bool = Depends(verify_admin_flexible),
) -> bool:
    """
    Admin verification dependency: accepts ADMIN_API_KEY/ADMIN_SECRET or session ADMIN role.
    """
    return is_admin



# -------------------------
# WebSocket Connection Manager
# -------------------------


class ConnectionManager:
    def __init__(
        self, max_connections_per_game: int = 50, max_total_connections: int = 500
    ):
        self.active: dict[str, list[WebSocket]] = {}
        self.max_connections_per_game = max_connections_per_game
        self.max_total_connections = max_total_connections
        self._connection_lock = asyncio.Lock()

    @property
    def total_connections(self) -> int:
        return sum(len(conns) for conns in self.active.values())

    async def connect(self, game_id: str, websocket: WebSocket) -> bool:
        async with self._connection_lock:
            if self.total_connections >= self.max_total_connections:
                return False
            game_conns = self.active.setdefault(game_id, [])
            if len(game_conns) >= self.max_connections_per_game:
                return False
            await websocket.accept()
            game_conns.append(websocket)
            return True

    def disconnect(self, game_id: str, websocket: WebSocket):
        if game_id in self.active:
            if websocket in self.active[game_id]:
                self.active[game_id].remove(websocket)
            if not self.active[game_id]:
                del self.active[game_id]

    async def close_game_connections(self, game_id: str, reason: str) -> None:
        for websocket in list(self.active.get(game_id, [])):
            try:
                await websocket.close(code=1000, reason=reason)
            except (WebSocketDisconnect, OSError, RuntimeError) as exc:
                logger.warning("WebSocket close failed for game %s: %s", game_id, exc)
            finally:
                self.disconnect(game_id, websocket)

    async def broadcast(self, game_id: str, message: dict):
        if game_id not in self.active:
            return
        for ws in list(self.active[game_id]):
            try:
                await ws.send_json(message)
            except WebSocketDisconnect:
                self.disconnect(game_id, ws)
            except (OSError, RuntimeError) as exc:
                logger.warning("WebSocket send failed for game %s: %s", game_id, exc)
                self.disconnect(game_id, ws)


manager = ConnectionManager()


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    if not re.match(r"^[a-zA-Z0-9_\-]+$", game_id) or len(game_id) > 64:
        await websocket.close(code=1008, reason="Invalid game ID format")
        return

    # Validate Origin header against CORS allowlist to prevent cross-origin
    # WebSocket hijacking. A malicious site could otherwise silently connect
    # and stream game state (drawn numbers, celebrations) for any game.
    origin = websocket.headers.get("origin")
    if origin and "*" not in cors_origins:
        if origin not in cors_origins:
            await websocket.close(code=1008, reason="Origin not allowed")
            return

    await _expire_inactive_games()
    game = db.games.get(game_id)
    if game and game.get("status") != "active":
        await websocket.close(code=1008, reason="This game is no longer active")
        return
    policy = game.get("access_policy", "LINK_ONLY") if game else "LINK_ONLY"

    if policy != "PUBLIC":
        authenticated = False
        session_factory = get_sessionmaker()
        async with session_factory() as db_session:
            # 1. Check session cookie
            session_cookie = websocket.cookies.get(SESSION_COOKIE_NAME)
            if session_cookie:
                user = await get_session_user(db_session, session_cookie)
                if user:
                    authenticated = True

            # 2. Check admin key from a header only; secrets must not be sent in URLs.
            admin_key = get_admin_api_key()
            x_admin_key = websocket.headers.get("x-admin-key")
            token = websocket.query_params.get("token")

            if not authenticated and admin_key:
                if x_admin_key and secrets.compare_digest(x_admin_key, admin_key):
                    authenticated = True
            # 3. Check token query param (session token or player token)
            if not authenticated and token:
                user = await get_session_user(db_session, token)
                if user:
                    authenticated = True
                else:
                    from auth.player_access import validate_player_session
                    player_sess = await validate_player_session(db_session, token, game_id)
                    if player_sess:
                        authenticated = True

            # 4. Allow unauthenticated bootstrap only for development installations.
            if not authenticated:
                result = await db_session.execute(select(func.count(User.id)))
                total_users = result.scalar_one()
                if total_users == 0 and allow_open_bootstrap():
                    authenticated = True

        if not authenticated:
            await websocket.close(code=1008, reason="Authentication required. This game is not public.")
            return

    connected = await manager.connect(game_id, websocket)
    if not connected:
        await websocket.close(code=1008, reason="Connection limit reached")
        return

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(game_id, websocket)


async def broadcast_game_state(game_id: str):
    game = db.games.get(game_id)
    if not game:
        return
    state = _normalize_game_state(game_id)
    await manager.broadcast(game_id, {"type": "state_update", "state": state})


# -------------------------
# Game endpoints
# -------------------------


@app.post("/games/{game_id}/start")
async def start_game(
    req: CreateGameRequest,
    game_id: str = Path(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$"),
    current_user: Optional[User] = Depends(require_operator_with_bootstrap),
):
    await _expire_inactive_games()

    # Enforce per-user active games quota
    if current_user:
        from auth.quotas import check_active_games_quota
        await check_active_games_quota(current_user, exclude_game_id=game_id)

    async with db.get_lock(game_id):
        existing_game = db.games.get(game_id)
        if current_user and existing_game and existing_game.get("status") == "active":
            assert_resource_access(current_user, existing_game.get("owner_id"))

        active_count = db.count_active_games()
        if (
            (existing_game is None or existing_game.get("status") != "active")
            and active_count >= db.max_concurrent_games
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Concurrent game limit reached: {db.max_concurrent_games}. "
                    "Stop or expire an existing game before creating a new one."
                ),
            )

        engine = DrawEngine(max_number=req.ball_set)
        now = _utc_now()
        game_data = {
            "engine": engine,
            "drawn": engine.drawn,
            "mode": req.mode,
            "stage": req.stage,
            "ball_set": req.ball_set,
            "status": "active",
            "access_policy": getattr(req, "access_policy", "LINK_ONLY") or "LINK_ONLY",
            "owner_id": current_user.id if current_user else None,
            "created_at": now.isoformat(),
            "last_activity_at": now.isoformat(),
        }
        db.set_game(game_id, game_data)
        await broadcast_game_state(game_id)
        return {"message": f"Game {game_id} started", "config": req.model_dump()}


@app.post("/games/{game_id}/stage/{required_rows}")
async def set_stage(
    game_id: str = Path(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$"),
    required_rows: int = Path(..., ge=1, le=5),
    current_user: Optional[User] = Depends(require_operator_with_bootstrap),
):
    async with db.get_lock(game_id):
        game = db.games.get(game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        if game.get("status") != "active":
            raise HTTPException(status_code=409, detail="Game is not active")
        if current_user:
            assert_resource_access(current_user, game.get("owner_id"))
        game["stage"] = required_rows
        game["last_activity_at"] = _utc_now().isoformat()
        await broadcast_game_state(game_id)
        return {"game_id": game_id, "stage": required_rows}


@app.post("/games/{game_id}/draw")
async def draw_number(
    game_id: str = Path(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$"),
    current_user: Optional[User] = Depends(require_operator_with_bootstrap),
):
    async with db.get_lock(game_id):
        await _expire_inactive_games()
        game = db.games.get(game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        if game.get("status") != "active":
            raise HTTPException(status_code=409, detail="Game is not active")
        if current_user:
            assert_resource_access(current_user, game.get("owner_id"))
        num = game["engine"].draw()
        if num is None:
            game["status"] = "finished"
            game["ended_reason"] = "exhausted"
            game["ended_at"] = _utc_now().isoformat()
            game["last_activity_at"] = game["ended_at"]
            await broadcast_game_state(game_id)
            db.remove_game(game_id)
            await manager.close_game_connections(game_id, "Game completed")
            raise HTTPException(status_code=400, detail="No numbers left")
        # update state
        game["drawn"] = list(game["engine"].drawn)
        game["last_activity_at"] = _utc_now().isoformat()
        # broadcast
        await broadcast_game_state(game_id)
        return {"drawn_number": num, "all_drawn": game["drawn"]}


@app.get("/games/{game_id}/state", response_model=GameStateResponse)
async def game_state(
    request: Request,
    game_id: str = Path(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$"),
    x_player_session: Optional[str] = Header(None, alias="X-Player-Session"),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    authorization: Optional[str] = Header(None),
    db_session: AsyncSession = Depends(get_db_session),
):
    await _expire_inactive_games()
    game = db.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    policy = game.get("access_policy", "LINK_ONLY")
    state_payload = {
        "game_id": game_id,
        "drawn": list(game["drawn"]),
        "mode": game["mode"],
        "stage": game["stage"],
        "status": game["status"],
        "access_policy": policy,
        "last_activity_at": game.get("last_activity_at"),
    }

    if policy == "PUBLIC":
        return state_payload

    # Authenticate for non-public game
    # 1. Logged in user session
    current_user = await get_current_user(request=request, db=db_session)
    if current_user:
        return state_payload

    # 2. Admin key check
    admin_key = get_admin_api_key()
    if admin_key:
        if x_admin_key and secrets.compare_digest(x_admin_key, admin_key):
            return state_payload
        if authorization:
            parts = authorization.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                if secrets.compare_digest(parts[1], admin_key):
                    return state_payload

    # 3. Player session token header
    if x_player_session:
        from auth.player_access import validate_player_session
        player_sess = await validate_player_session(db_session, x_player_session, game_id)
        if player_sess:
            return state_payload

    # 4. Bootstrap mode (0 users and no admin key configured)
    result = await db_session.execute(select(func.count(User.id)))
    total_users = result.scalar_one()
    if total_users == 0 and allow_open_bootstrap():
        return state_payload

    raise HTTPException(status_code=401, detail="Authentication required. This game is not public.")


# -------------------------
# Card endpoints
# -------------------------


# public_id is a truncated (32-bit) SHA-256 hash, so a collision between
# two *different* cards, while rare, is not implausible at scale (birthday
# bound). Without this guard, a collision would silently overwrite the
# older card's stored grid/serial in db.cards, corrupting it for
# validation. Bounds how many times we'll regenerate a fresh grid before
# giving up.
MAX_ID_COLLISION_RETRIES = 5


@app.post("/cards/batch")
async def generate_cards(
    req: CardBatchRequest,
    current_user: Optional[User] = Depends(require_operator_with_bootstrap),
):
    if req.game_id:
        await _expire_inactive_games()
        target_game = db.games.get(req.game_id)
        if target_game and target_game.get("status") != "active":
            raise HTTPException(status_code=409, detail="Game is not active")

    # Enforce per-user persistent cards quota if persistence was requested
    if req.persistent and current_user:
        from auth.quotas import check_persistent_cards_quota
        await check_persistent_cards_quota(current_user, additional_cards=req.count)

    cards = []
    for _ in range(req.count):
        grid = generate_75_ball_card()
        serial = serialize_card(grid)
        public_id = short_id(serial)

        retries = 0
        while public_id in db.cards and db.cards[public_id]["serial"] != serial:
            retries += 1
            if retries > MAX_ID_COLLISION_RETRIES:
                raise HTTPException(
                    status_code=500,
                    detail="Could not allocate a unique card ID; please retry",
                )
            grid = generate_75_ball_card()
            serial = serialize_card(grid)
            public_id = short_id(serial)

        try:
            db.set_card(
                public_id,
                {
                    "grid": grid,
                    "serial": serial,
                    "game_id": req.game_id,
                    "owner_id": current_user.id if current_user else None,
                },
                persistent=req.persistent,
            )
        except PersistentStorageFullError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except PersistentStorageUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        cards.append(
            {
                "public_id": public_id,
                "serial": serial,
                "grid": grid,
                "persistent": req.persistent,
            }
        )
    if req.game_id:
        game = db.games.get(req.game_id)
        if game:
            game["last_activity_at"] = _utc_now().isoformat()
        await broadcast_game_state(req.game_id)
    return {"count": len(cards), "persistent": req.persistent, "cards": cards}


@app.get("/cards/{public_id}", response_model=CardResponse)
def get_card(
    public_id: str = Path(
        ..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$"
    )
):
    card = db.cards.get(public_id)
    if not card:
        return {
            "exists": False,
            "public_id": public_id,
            "serial": "",
            "grid": [],
            "persistent": False,
        }
    return {
        "exists": True,
        "public_id": public_id,
        "serial": card["serial"],
        "grid": card["grid"],
        "persistent": db.cards.is_persistent(public_id),
    }


@app.get("/games/{game_id}/cards")
def get_game_cards(
    game_id: str = Path(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$"),
    current_user: Optional[User] = Depends(require_operator_with_bootstrap),
):
    """Get all cards for a specific game (admin: all, operator: own only)."""
    game = db.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if current_user:
        assert_resource_access(current_user, game.get("owner_id"))

    game_cards = []
    for public_id, card_data in db.cards.items():
        if card_data.get("game_id") == game_id:
            # Operators can only see their own cards; ADMIN sees all
            if current_user and not has_role(current_user, "ADMIN"):
                card_owner = card_data.get("owner_id")
                if card_owner is not None and card_owner != current_user.id:
                    continue
            game_cards.append(
                {
                    "public_id": public_id,
                    "serial": card_data["serial"],
                    "grid": card_data["grid"],
                    "persistent": db.cards.is_persistent(public_id),
                }
            )
    return {"count": len(game_cards), "cards": game_cards}


# -------------------------
# Validation endpoint
# -------------------------


@app.post("/validate", response_model=ValidateResponse)
async def validate(req: ValidateRequest):
    game = db.games.get(req.game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Cards are reusable artifacts (like a physical bingo card): the same
    # card can legitimately be validated against many different game
    # sessions over time, not just the one it happened to be generated
    # alongside. `card["game_id"]` is kept only as informational metadata
    # (used by GET /games/{game_id}/cards to list cards issued for a
    # particular batch/session) and is never used to gate validation.
    # This doesn't create a win-forging risk: card content is fixed and
    # randomly generated at creation time, independent of which game it's
    # later checked against, so a player can only find out whether their
    # existing card matches the current game's drawn numbers - they can't
    # choose a card to guarantee a win.
    card = db.cards.get(req.serial)
    if not card:
        return {
            "valid": False,
            "details": {"error": "Card does not exist"},
            "drawn": list(game["drawn"]),
            "grid": [],
            "public_id": req.serial,
        }

    valid, details = validate_card(game, card)

    # if valid, broadcast a celebration event
    if valid:
        await manager.broadcast(
            req.game_id,
            {"type": "celebration", "card_id": req.serial, "details": details},
        )

    return {
        "valid": valid,
        "details": details,
        "drawn": list(game["drawn"]),
        "grid": card["grid"],
        "public_id": req.serial,
    }
