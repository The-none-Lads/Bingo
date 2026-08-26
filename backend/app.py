import os
import re
import secrets
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Path,
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
    GameStateResponse,
    ValidateRequest,
    ValidateResponse,
)
from storage.db import db

load_dotenv()


def get_bool_env(key: str, default: bool = True) -> bool:
    """Get boolean from environment variable."""
    value = os.getenv(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


def is_docs_enabled() -> bool:
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env == "production":
        return get_bool_env("ENABLE_DOCS", False)
    return get_bool_env("ENABLE_DOCS", True)


app = FastAPI(
    title="Bingo Game API",
    docs_url="/docs" if is_docs_enabled() else None,
    redoc_url="/redoc" if is_docs_enabled() else None,
    openapi_url="/openapi.json" if is_docs_enabled() else None,
)


# Configuration from environment variables
def get_cors_origins() -> List[str]:
    """Get CORS origins from environment variable or safe defaults."""
    origins_str = os.getenv("CORS_ORIGINS")
    if origins_str is None or not origins_str.strip():
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

    if origins_str.strip() == "*":
        return ["*"]

    return [origin.strip() for origin in origins_str.split(",") if origin.strip()]


cors_origins = get_cors_origins()
allow_credentials = get_bool_env("CORS_ALLOW_CREDENTIALS", True)
# Enforce W3C/Fetch standard: wildcard origin cannot be used with credentials
if "*" in cors_origins:
    allow_credentials = False

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# -------------------------
# Authentication / Authorization
# -------------------------


async def verify_admin(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    authorization: Optional[str] = Header(None),
) -> bool:
    """
    Lightweight admin authorization verification.
    If ADMIN_API_KEY or ADMIN_SECRET is configured, validates credentials.
    If neither is configured, allows open access for development/private instances.
    """
    admin_key = os.getenv("ADMIN_API_KEY") or os.getenv("ADMIN_SECRET")
    if not admin_key:
        return True

    if x_admin_key and secrets.compare_digest(x_admin_key, admin_key):
        return True

    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            if secrets.compare_digest(parts[1], admin_key):
                return True

    raise HTTPException(
        status_code=401,
        detail="Unauthorized: Admin authentication required",
    )


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

    @property
    def total_connections(self) -> int:
        return sum(len(conns) for conns in self.active.values())

    async def connect(self, game_id: str, websocket: WebSocket) -> bool:
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

    async def broadcast(self, game_id: str, message: dict):
        if game_id not in self.active:
            return
        for ws in list(self.active[game_id]):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(game_id, ws)


manager = ConnectionManager()


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    if not re.match(r"^[a-zA-Z0-9_\-]+$", game_id) or len(game_id) > 64:
        await websocket.close(code=1008, reason="Invalid game ID format")
        return

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


async def broadcast_game_state(game_id: str):
    game = db.games.get(game_id)
    if not game:
        return
    state = {
        "game_id": game_id,
        "drawn": list(game["drawn"]),
        "mode": game["mode"],
        "stage": game["stage"],
        "status": game["status"],
    }
    await manager.broadcast(game_id, {"type": "state_update", "state": state})


# -------------------------
# Game endpoints
# -------------------------


@app.post("/games/{game_id}/start")
async def start_game(
    req: CreateGameRequest,
    game_id: str = Path(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$"),
    _admin: bool = Depends(verify_admin),
):
    async with db.get_lock(game_id):
        engine = DrawEngine(max_number=req.ball_set)
        db.set_game(
            game_id,
            {
                "engine": engine,
                "drawn": engine.drawn,
                "mode": req.mode,
                "stage": req.stage,
                "ball_set": req.ball_set,
                "status": "active",
            },
        )
        await broadcast_game_state(game_id)
        return {"message": f"Game {game_id} started", "config": req.model_dump()}


@app.post("/games/{game_id}/stage/{required_rows}")
async def set_stage(
    game_id: str = Path(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$"),
    required_rows: int = Path(..., ge=1, le=5),
    _admin: bool = Depends(verify_admin),
):
    async with db.get_lock(game_id):
        game = db.games.get(game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        game["stage"] = required_rows
        await broadcast_game_state(game_id)
        return {"game_id": game_id, "stage": required_rows}


@app.post("/games/{game_id}/draw")
async def draw_number(
    game_id: str = Path(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$"),
    _admin: bool = Depends(verify_admin),
):
    async with db.get_lock(game_id):
        game = db.games.get(game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        num = game["engine"].draw()
        if num is None:
            game["status"] = "finished"
            raise HTTPException(status_code=400, detail="No numbers left")
        # update state
        game["drawn"] = list(game["engine"].drawn)
        # broadcast
        await broadcast_game_state(game_id)
        return {"drawn_number": num, "all_drawn": game["drawn"]}


@app.get("/games/{game_id}/state", response_model=GameStateResponse)
def game_state(
    game_id: str = Path(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")
):
    game = db.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return {
        "game_id": game_id,
        "drawn": list(game["drawn"]),
        "mode": game["mode"],
        "stage": game["stage"],
        "status": game["status"],
    }


# -------------------------
# Card endpoints
# -------------------------


@app.post("/cards/batch")
async def generate_cards(
    req: CardBatchRequest,
    _admin: bool = Depends(verify_admin),
):
    cards = []
    for _ in range(req.count):
        grid = generate_75_ball_card()
        serial = serialize_card(grid)
        public_id = short_id(serial)
        db.set_card(
            public_id,
            {"grid": grid, "serial": serial, "game_id": req.game_id},
        )
        cards.append({"public_id": public_id, "serial": serial, "grid": grid})
    if req.game_id:
        await broadcast_game_state(req.game_id)
    return {"count": len(cards), "cards": cards}


@app.get("/cards/{public_id}", response_model=CardResponse)
def get_card(
    public_id: str = Path(
        ..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$"
    )
):
    card = db.cards.get(public_id)
    if not card:
        return {"exists": False, "public_id": public_id, "serial": "", "grid": []}
    return {
        "exists": True,
        "public_id": public_id,
        "serial": card["serial"],
        "grid": card["grid"],
    }


@app.get("/games/{game_id}/cards")
def get_game_cards(
    game_id: str = Path(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$"),
    _admin: bool = Depends(verify_admin),
):
    """Get all cards for a specific game"""
    game_cards = []
    for public_id, card_data in db.cards.items():
        if card_data.get("game_id") == game_id:
            game_cards.append(
                {
                    "public_id": public_id,
                    "serial": card_data["serial"],
                    "grid": card_data["grid"],
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

    card = db.cards.get(req.serial)
    if not card or (card.get("game_id") and card["game_id"] != req.game_id):
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
