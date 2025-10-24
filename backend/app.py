from fastapi import FastAPI, HTTPException
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


# -------------------------
# Game endpoints
# -------------------------

@app.post("/games/{game_id}/start")
def start_game(game_id: str, req: CreateGameRequest):
    engine = DrawEngine(max_number=req.ball_set)
    db.games[game_id] = {
        "engine": engine,
        "drawn": engine.drawn,
        "mode": req.mode,
        "stage": req.stage,
        "ball_set": req.ball_set,
        "status": "active"
    }
    return {"message": f"Game {game_id} started", "config": req.dict()}


@app.post("/games/{game_id}/stage/{required_rows}")
def set_stage(game_id: str, required_rows: int):
    game = db.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    game["stage"] = required_rows
    return {"game_id": game_id, "stage": required_rows}


@app.post("/games/{game_id}/draw")
def draw_number(game_id: str):
    game = db.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    num = game["engine"].draw()
    if num is None:
        raise HTTPException(status_code=400, detail="No numbers left")
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
def generate_cards(req: CardBatchRequest):
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
    return {"count": len(cards), "cards": cards}


@app.get("/cards/{public_id}")
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

@app.post("/validate")
def validate(req: ValidateRequest):
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
    return {
        "valid": valid,
        "details": details,
        "drawn": game["drawn"],
        "grid": card["grid"],
        "public_id": req.serial
    }
