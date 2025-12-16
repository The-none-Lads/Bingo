import os
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
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

app = FastAPI()

load_dotenv()


# Configuration from environment variables
def get_cors_origins() -> List[str]:
    """Get CORS origins from environment variable."""
    origins_str = os.getenv("CORS_ORIGINS")
    if origins_str is None:
        raise RuntimeError("CORS_ORIGINS must be set")

    if origins_str.strip() == "*":
        return ["*"]

    return [origin.strip() for origin in origins_str.split(",") if origin.strip()]


def get_bool_env(key: str, default: bool = True) -> bool:
    """Get boolean from environment variable."""
    value = os.getenv(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=get_bool_env("CORS_ALLOW_CREDENTIALS", True),
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# Game endpoints
# -------------------------

connections: List[WebSocket] = []


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, game_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active.setdefault(game_id, []).append(websocket)

    def disconnect(self, game_id: str, websocket: WebSocket):
        if game_id in self.active:
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
    await manager.connect(game_id, websocket)
    try:
        while True:
            await websocket.receive_text()
            # optionally ignore or log
    except WebSocketDisconnect:
        manager.disconnect(game_id, websocket)


async def broadcast_game_state(game_id: str):
    game = db.games.get(game_id)
    if not game:
        return
    state = {
        "game_id": game_id,
        "drawn": game["drawn"],
        "mode": game["mode"],
        "stage": game["stage"],
        "status": game["status"],
    }
    await manager.broadcast(game_id, {"type": "state_update", "state": state})


@app.post("/games/{game_id}/start")
async def start_game(game_id: str, req: CreateGameRequest):
    engine = DrawEngine(max_number=req.ball_set)
    db.games[game_id] = {
        "engine": engine,
        "drawn": engine.drawn,
        "mode": req.mode,
        "stage": req.stage,
        "ball_set": req.ball_set,
        "status": "active",
    }
    # broadcast new state
    await broadcast_game_state(game_id)
    return {"message": f"Game {game_id} started", "config": req.model_dump()}


@app.post("/games/{game_id}/stage/{required_rows}")
async def set_stage(game_id: str, required_rows: int):
    game = db.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    game["stage"] = required_rows
    await broadcast_game_state(game_id)
    return {"game_id": game_id, "stage": required_rows}


@app.post("/games/{game_id}/draw")
async def draw_number(game_id: str):
    game = db.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    num = game["engine"].draw()
    if num is None:
        raise HTTPException(status_code=400, detail="No numbers left")
    # update state
    game["drawn"] = game["engine"].drawn
    # broadcast
    await broadcast_game_state(game_id)
    return {"drawn_number": num, "all_drawn": game["drawn"]}


@app.get("/games/{game_id}/state", response_model=GameStateResponse)
def game_state(game_id: str):
    game = db.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return {
        "game_id": game_id,
        "drawn": game["drawn"],
        "mode": game["mode"],
        "stage": game["stage"],
        "status": game["status"],
    }


# -------------------------
# Card endpoints
# -------------------------


@app.post("/cards/batch")
async def generate_cards(req: CardBatchRequest):
    cards = []
    for _ in range(req.count):
        grid = generate_75_ball_card()
        serial = serialize_card(grid)
        public_id = short_id(serial)
        db.cards[public_id] = {"grid": grid, "serial": serial, "game_id": req.game_id}
        cards.append({"public_id": public_id, "serial": serial, "grid": grid})
    # optional: broadcast updated state
    await broadcast_game_state(req.game_id)
    return {"count": len(cards), "cards": cards}


@app.get("/cards/{public_id}", response_model=CardResponse)
def get_card(public_id: str):
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
def get_game_cards(game_id: str):
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
    if not card:
        return {
            "valid": False,
            "details": {"error": "Card does not exist"},
            "drawn": game["drawn"],
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
        "drawn": game["drawn"],
        "grid": card["grid"],
        "public_id": req.serial,
    }
