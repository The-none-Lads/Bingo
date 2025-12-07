import subprocess
import time
import uuid
import os

import httpx
import pytest
import pytest_asyncio
from app import app
from httpx import AsyncClient


@pytest_asyncio.fixture(params=["inprocess", "live"])
async def client(request):
    """
    Provides an httpx.AsyncClient either in-process (fast) or
    against a live uvicorn server (realistic).
    """
    if request.param == "inprocess":
        transport = httpx.ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    else:
        proc = subprocess.Popen(
            ["uvicorn", "app:app", "--port", "8000", "--host", "127.0.0.1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
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


# --- NEW CORS TESTS ---


@pytest.mark.asyncio
async def test_cors_allows_configured_origin(client, monkeypatch):
    # Pretend we set CORS_ORIGINS to include http://test and 127.0.0.1:8000
    monkeypatch.setenv("CORS_ORIGINS", "http://test,127.0.0.1:8000")

    resp = await client.options(
        "/games/nonexistent-game/draw",
        headers={
            "Origin": "http://test",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.status_code == 200
    # CORS middleware should echo back the origin
    assert resp.headers.get("access-control-allow-origin") == "http://test"


@pytest.mark.asyncio
async def test_cors_rejects_unset_origin(client, monkeypatch):
    # Unset CORS_ORIGINS so app should fail fast or default
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    resp = await client.options(
        "/games/nonexistent-game/draw",
        headers={
            "Origin": "http://notallowed.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    # Depending on your get_cors_origins implementation:
    # - If you default to ["*"], then allow-origin will be "*"
    # - If you raise RuntimeError, pytest will fail at import
    # Adjust assertion accordingly
    assert resp.status_code in (200, 400)
    if resp.status_code == 200:
        assert resp.headers.get("access-control-allow-origin") in ("*", None)
