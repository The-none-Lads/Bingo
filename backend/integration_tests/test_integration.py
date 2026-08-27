import asyncio
import os
import subprocess
import sys
import uuid

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
        # Run live uvicorn server via current python executable
        backend_dir = os.path.join(os.path.dirname(__file__), "..")
        env = os.environ.copy()

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app:app",
                "--port",
                "8000",
                "--host",
                "127.0.0.1",
            ],
            cwd=backend_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Wait for server readiness
        ready = False
        max_attempts = 30
        for _ in range(max_attempts):
            await asyncio.sleep(0.2)

            try:
                async with httpx.AsyncClient(
                    base_url="http://127.0.0.1:8000",
                    timeout=1.0,
                ) as check_client:
                    r = await check_client.get("/games/health-check/state")

                    if r.status_code in (200, 404):
                        ready = True
                        break

            except httpx.HTTPError:
                pass

        if not ready:
            stdout, stderr = proc.communicate(timeout=1)
            raise RuntimeError(
                f"Uvicorn failed to start.\nSTDOUT:\n{stdout.decode()}\nSTDERR:\n{stderr.decode()}"
            )

        try:
            async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as ac:
                yield ac
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()


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


# --- CORS TESTS ---


""" @pytest.mark.asyncio
async def test_cors_allows_configured_origin(client):
    # Start the game
    resp = await client.post(
        f"/games/test-cors-game/start",
        json={"mode": "regular", "stage": 1, "ball_set": 75},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert "message" in payload

    resp = await client.options(
        "/games/test-cors-game/state",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    # CORS middleware should allow localhost:3000
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_cors_rejects_unauthorized_origin(client):
    resp = await client.options(
        "/games/test-cors-game/state",
        headers={
            "Origin": "http://malicious-site.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code in (200, 400)
    assert (
        resp.headers.get("access-control-allow-origin") != "http://malicious-site.com"
    ) """
