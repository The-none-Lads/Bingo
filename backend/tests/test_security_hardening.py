import asyncio

import pytest
from app import app, manager
from fastapi.testclient import TestClient
from logic.cards import generate_75_ball_card, serialize_card, short_id
from storage.db import MemoryDB, db


@pytest.fixture(autouse=True)
def clean_db():
    db.clear()
    yield
    db.clear()


@pytest.fixture
def client():
    return TestClient(app)


class TestInputValidationHardening:
    """Verify strict validation and rejection of invalid inputs."""

    def test_invalid_game_mode_rejected(self, client):
        response = client.post(
            "/games/test_game/start",
            json={"mode": "invalid_mode_xyz", "ball_set": 75, "stage": 1},
        )
        assert response.status_code == 422

    def test_ball_set_out_of_bounds_rejected(self, client):
        # ball_set must be between 1 and 100
        for invalid_set in [0, -10, 101, 500]:
            response = client.post(
                "/games/test_game/start",
                json={"mode": "progressive_rows", "ball_set": invalid_set, "stage": 1},
            )
            assert response.status_code == 422

    def test_stage_out_of_bounds_rejected(self, client):
        # stage must be between 1 and 5
        for invalid_stage in [0, 6, -1, 10]:
            response = client.post(
                "/games/test_game/start",
                json={
                    "mode": "progressive_rows",
                    "ball_set": 75,
                    "stage": invalid_stage,
                },
            )
            assert response.status_code == 422

    def test_invalid_game_id_characters_rejected(self, client):
        invalid_ids = [
            "game/../../bad",
            "game<script>",
            "game with spaces",
            "game#1",
            "a" * 100,  # too long (>64)
        ]
        for bad_id in invalid_ids:
            response = client.post(
                f"/games/{bad_id}/start",
                json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
            )
            assert response.status_code in (404, 422)

    def test_card_batch_count_bounds_rejected(self, client):
        # count must be between 1 and 500
        for invalid_count in [0, -5, 501, 100000]:
            response = client.post(
                "/cards/batch",
                json={"count": invalid_count, "game_id": "test_game"},
            )
            assert response.status_code == 422

    def test_set_stage_bounds_rejected(self, client):
        client.post(
            "/games/test_game/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
        )
        for bad_stage in [0, 6, -1]:
            response = client.post(f"/games/test_game/stage/{bad_stage}")
            assert response.status_code == 422


class TestAdminAuthorizationHardening:
    """Verify that privileged operations enforce admin auth when configured."""

    def test_admin_auth_required_when_secret_set(self, monkeypatch):
        secret = "super-secret-admin-key-12345"
        monkeypatch.setenv("ADMIN_API_KEY", secret)
        test_client = TestClient(app)

        # 1. Unauthenticated request to privileged endpoint is rejected (401)
        res_start = test_client.post(
            "/games/secure_game/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
        )
        assert res_start.status_code == 401

        res_draw = test_client.post("/games/secure_game/draw")
        assert res_draw.status_code == 401

        res_batch = test_client.post(
            "/cards/batch",
            json={"count": 5, "game_id": "secure_game"},
        )
        assert res_batch.status_code == 401

        # 2. Request with invalid header key is rejected (401)
        res_bad_key = test_client.post(
            "/games/secure_game/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
            headers={"X-Admin-Key": "wrong-key"},
        )
        assert res_bad_key.status_code == 401

        # 3. Request with valid X-Admin-Key header succeeds (200)
        res_ok_header = test_client.post(
            "/games/secure_game/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
            headers={"X-Admin-Key": secret},
        )
        assert res_ok_header.status_code == 200

        # 4. Request with valid Bearer token succeeds (200)
        res_ok_bearer = test_client.post(
            "/games/secure_game/draw",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert res_ok_bearer.status_code == 200

        # 5. Public read endpoints remain open without auth
        res_state = test_client.get("/games/secure_game/state")
        assert res_state.status_code == 200

        res_validate = test_client.post(
            "/validate",
            json={"game_id": "secure_game", "serial": "NONEXIST"},
        )
        assert res_validate.status_code == 200


class TestAuthoritativeDrawIntegrityAndConcurrency:
    """Verify draw concurrency protection and game state integrity."""

    @pytest.mark.asyncio
    async def test_concurrent_draws_no_duplicates(self):
        """Simulate rapid concurrent draw requests using asyncio."""
        game_id = "concurrent_game"
        from logic.draws import DrawEngine

        engine = DrawEngine(max_number=75)
        db.set_game(
            game_id,
            {
                "engine": engine,
                "drawn": engine.drawn,
                "mode": "progressive_rows",
                "stage": 1,
                "ball_set": 75,
                "status": "active",
            },
        )

        async def perform_draw():
            async with db.get_lock(game_id):
                game = db.games.get(game_id)
                num = game["engine"].draw()
                if num is not None:
                    game["drawn"] = list(game["engine"].drawn)
                return num

        # Draw 50 numbers concurrently
        results = await asyncio.gather(*[perform_draw() for _ in range(50)])
        valid_numbers = [n for n in results if n is not None]

        # Ensure all 50 drawn numbers are unique and match game state
        assert len(valid_numbers) == 50
        assert len(set(valid_numbers)) == 50
        assert db.games[game_id]["drawn"] == valid_numbers

    def test_game_status_transitions_to_finished(self, client):
        client.post(
            "/games/small_game/start",
            json={"mode": "progressive_rows", "ball_set": 3, "stage": 1},
        )
        for _ in range(3):
            res = client.post("/games/small_game/draw")
            assert res.status_code == 200

        # 4th draw exhausts numbers and sets status to finished
        res_exhausted = client.post("/games/small_game/draw")
        assert res_exhausted.status_code == 400
        state = client.get("/games/small_game/state").json()
        assert state["status"] == "finished"


class TestCardIsolationAndCollisionProtection:
    """Verify card validation isolation and capacity bounds."""

    def test_card_reusable_across_different_games(self, client):
        """Cards are reusable artifacts (like a physical bingo card): the
        same card can be validated against a different game session than
        the one it happened to be generated alongside. Card content is
        fixed and random at creation time regardless of which game it's
        later checked against, so this doesn't let a player choose a
        winning card."""
        client.post(
            "/games/game_A/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
        )
        client.post(
            "/games/game_B/start",
            json={"mode": "full_house", "ball_set": 75, "stage": 1},
        )

        # Generate card for game_A
        cards_resp = client.post(
            "/cards/batch",
            json={"count": 1, "game_id": "game_A"},
        ).json()
        card = cards_resp["cards"][0]

        # Force every number on the card to be "drawn" in game_B, so a
        # correctly-wired cross-game validation reports a win there.
        for row in card["grid"]:
            for num in row:
                if num != "FREE":
                    db.games["game_B"]["drawn"].append(num)

        # Validate against game_B, a different game than it was generated for
        val_resp = client.post(
            "/validate",
            json={"game_id": "game_B", "serial": card["public_id"]},
        )
        assert val_resp.status_code == 200
        data = val_resp.json()
        assert data["valid"] is True
        assert data["grid"] == card["grid"]

    def test_memory_db_capacity_bounds(self):
        small_db = db.__class__(max_games=5, max_cards=10, card_db_path=":memory:")
        for i in range(10):
            small_db.set_game(f"game_{i}", {"status": "active"})
            small_db.set_card(
                f"card_{i}", {"serial": f"s_{i}", "game_id": None, "grid": []}
            )

        assert len(small_db.games) <= 5
        assert len(small_db.cards) <= 10

    def test_forced_public_id_collision_does_not_overwrite_existing_card(
        self, client, monkeypatch
    ):
        """public_id is a truncated (32-bit) hash of the card's serial, so a
        collision between two *different* cards is possible. Regression:
        this must not silently overwrite the older card's stored
        grid/serial in db.cards."""
        import app as app_module

        calls = {"n": 0}
        real_short_id = app_module.short_id

        def colliding_short_id(serial, length=8):
            calls["n"] += 1
            if calls["n"] <= 2:
                # Force the first two generated cards to collide on
                # public_id regardless of their (different) serials.
                return "COLLIDE1"
            return real_short_id(serial, length)

        monkeypatch.setattr(app_module, "short_id", colliding_short_id)

        response = client.post(
            "/cards/batch", json={"count": 2, "game_id": "collision_test"}
        )
        assert response.status_code == 200
        data = response.json()

        ids = [c["public_id"] for c in data["cards"]]
        assert len(set(ids)) == 2, "colliding cards must not share a public_id"
        for card in data["cards"]:
            stored = db.cards[card["public_id"]]
            assert stored["serial"] == card["serial"]
            assert stored["grid"] == card["grid"]


class TestCardPersistenceAcrossRestart:
    """Cards must survive the backend process being closed and restarted.

    These use a real temp file (not :memory:) specifically to prove disk
    persistence works, since the rest of the suite intentionally runs
    against :memory: for speed/isolation (see conftest.py).
    """

    def test_card_survives_simulated_restart(self, tmp_path):
        db_path = str(tmp_path / "cards.db")

        # "Backend process 1": generate and store a card.
        first_instance = MemoryDB(card_db_path=db_path)
        grid = generate_75_ball_card()
        serial = serialize_card(grid)
        public_id = short_id(serial)
        first_instance.set_card(
            public_id, {"serial": serial, "game_id": "night_1", "grid": grid}
        )
        first_instance.close()  # simulates the backend process exiting

        # "Backend process 2": a brand new MemoryDB pointed at the same
        # file must see the card without ever being told about it again.
        second_instance = MemoryDB(card_db_path=db_path)
        assert public_id in second_instance.cards
        assert second_instance.cards[public_id]["serial"] == serial
        assert second_instance.cards[public_id]["grid"] == grid
        second_instance.close()

    def test_card_eviction_is_also_removed_from_disk(self, tmp_path):
        db_path = str(tmp_path / "cards.db")
        instance = MemoryDB(max_cards=2, card_db_path=db_path)
        for i in range(3):
            instance.set_card(
                f"card_{i}", {"serial": f"s_{i}", "game_id": None, "grid": []}
            )
        instance.close()

        # card_0 should have been evicted (oldest) both in memory and on disk.
        reloaded = MemoryDB(card_db_path=db_path)
        assert "card_0" not in reloaded.cards
        assert "card_1" in reloaded.cards
        assert "card_2" in reloaded.cards
        reloaded.close()

    def test_clear_also_clears_disk(self, tmp_path):
        db_path = str(tmp_path / "cards.db")
        instance = MemoryDB(card_db_path=db_path)
        instance.set_card("card_x", {"serial": "s_x", "game_id": None, "grid": []})
        instance.clear()
        instance.close()

        reloaded = MemoryDB(card_db_path=db_path)
        assert reloaded.cards == {}
        reloaded.close()


class TestWebSocketSecurity:
    """Verify WebSocket connection limits and clean lifecycle."""

    def test_websocket_invalid_game_id_rejection(self, client):
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect) as excinfo:
            with client.websocket_connect("/ws/invalid_id!@#special") as ws:
                ws.receive_text()
        assert excinfo.value.code == 1008

    def test_websocket_connection_limits(self):
        cm = manager.__class__(max_connections_per_game=2, max_total_connections=3)
        assert cm.max_connections_per_game == 2
        assert cm.max_total_connections == 3
