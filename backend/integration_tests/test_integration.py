import subprocess
import time
import uuid

import httpx
import pytest
from app import app
from httpx import AsyncClient


@pytest.fixture(params=["inprocess", "live"])
async def client(request):
    """
    Provides an httpx.AsyncClient either in-process (fast) or
    against a live uvicorn server (realistic).
    """
    if request.param == "inprocess":
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    else:
        # Start uvicorn in a subprocess
        proc = subprocess.Popen(
            ["uvicorn", "app:app", "--port", "8000", "--host", "127.0.0.1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Give the server a moment to boot
        time.sleep(1.5)
        try:
            async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as ac:
                yield ac
        finally:
            proc.terminate()
            proc.wait()


@pytest.mark.asyncio
async def test_full_game_flow(client):
    """
    Integration test that exercises a full game flow:
    - start a game
    - fetch game state
    - generate a batch of cards
    - retrieve a card
    - draw a number
    - validate a card
    """
    game_id = f"test-{uuid.uuid4().hex[:8]}"

    # Start the game
    resp = await client.post(
        f"/games/{game_id}/start",
        json={"mode": "regular", "stage": 1, "ball_set": 75},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert "message" in payload

    # Get game state
    resp = await client.get(f"/games/{game_id}/state")
    assert resp.status_code == 200
    state = resp.json()
    assert state["game_id"] == game_id
    assert state["status"] == "active"
    assert isinstance(state["drawn"], list)

    # Generate a small batch of cards
    resp = await client.post("/cards/batch", json={"count": 3, "game_id": game_id})
    assert resp.status_code == 200
    batch = resp.json()
    assert batch["count"] == 3
    assert len(batch["cards"]) == 3

    # Inspect first card
    first = batch["cards"][0]
    public_id = first["public_id"]
    assert "serial" in first and "grid" in first

    # Retrieve card by public_id
    resp = await client.get(f"/cards/{public_id}")
    assert resp.status_code == 200
    card_resp = resp.json()
    assert card_resp["exists"] is True
    assert card_resp["public_id"] == public_id

    # Draw a number
    resp = await client.post(f"/games/{game_id}/draw")
    assert resp.status_code == 200
    draw_payload = resp.json()
    assert "drawn_number" in draw_payload
    assert draw_payload["drawn_number"] in draw_payload["all_drawn"]

    # Validate the card
    resp = await client.post(
        "/validate", json={"game_id": game_id, "serial": public_id}
    )
    assert resp.status_code == 200
    val = resp.json()
    assert "valid" in val and isinstance(val["valid"], bool)
    assert val["public_id"] == public_id
    assert isinstance(val["drawn"], list)


@pytest.mark.asyncio
async def test_draw_on_nonexistent_game_returns_404(client):
    resp = await client.post("/games/nonexistent-game/draw")
    assert resp.status_code == 404
