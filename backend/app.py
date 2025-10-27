from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from logic.draws import DrawEngine
from logic.cards import generate_75_ball_card, serialize_card, short_id
from logic.validate import validate_card
from storage.db import db
from models import (
    CreateGameRequest,
    CardBatchRequest,
    ValidateRequest,
    GameStateResponse,
    CardResponse,
    ValidateResponse,
)


app = FastAPI()

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to ["http://localhost:5173"] for your Vite dev server
    allow_credentials=True,
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
            # optional: receive messages from client
            await websocket.receive_text()
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
        "status": "active"
    }
    # broadcast new state
    await broadcast_game_state(game_id)
    return {"message": f"Game {game_id} started", "config": req.dict()}



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
        "status": game["status"]
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
        db.cards[public_id] = {
            "grid": grid,
            "serial": serial,
            "game_id": req.game_id
        }
        cards.append({"public_id": public_id, "serial": serial, "grid": grid})
    # optional: broadcast updated state
    await broadcast_game_state(req.game_id)
    return {"count": len(cards), "cards": cards}



@app.get("/cards/{public_id}", response_model=CardResponse)
def get_card(public_id: str):
    card = db.cards.get(public_id)
    if not card:
        return {
            "exists": False,
            "public_id": public_id,
            "serial": "",
            "grid": []
        }
    return {
        "exists": True,
        "public_id": public_id,
        "serial": card["serial"],
        "grid": card["grid"]
    }


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
            "public_id": req.serial
        }

    valid, details = validate_card(game, card)

    # if valid, broadcast a celebration event
    if valid:
        await manager.broadcast(req.game_id, {
            "type": "celebration",
            "card_id": req.serial,
            "details": details
        })

    return {
        "valid": valid,
        "details": details,
        "drawn": game["drawn"],
        "grid": card["grid"],
        "public_id": req.serial
    }
