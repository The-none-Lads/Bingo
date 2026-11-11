import asyncio

import pytest
from app import ConnectionManager, app, manager
from auth.config import allow_open_bootstrap
from auth.dependencies import verify_admin_flexible
from auth.rbac import require_operator_with_bootstrap
from fastapi import HTTPException
from fastapi.testclient import TestClient
from logic.cards import generate_75_ball_card, serialize_card, short_id
from storage.db import MemoryDB, PersistentStorageFullError, db


@pytest.fixture(autouse=True)
def clean_db():
    db.clear()
    yield
    db.clear()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


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

    def test_admin_auth_required_when_secret_set(self, monkeypatch, client):
        secret = "super-secret-admin-key-12345"
        monkeypatch.setenv("ADMIN_API_KEY", secret)

        # With ADMIN_API_KEY set, bootstrap mode is disabled
        # Unauthenticated request should be rejected (401)
        res_start = client.post(
            "/games/secure_game/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
        )
        # When ADMIN_API_KEY is set, verify_admin_flexible rejects with 401
        assert res_start.status_code == 401

        res_draw = client.post("/games/secure_game/draw")
        assert res_draw.status_code == 401

        res_batch = client.post(
            "/cards/batch",
            json={"count": 5, "game_id": "secure_game"},
        )
        assert res_batch.status_code == 401

        # 2. Request with invalid header key is rejected (401)
        res_bad_key = client.post(
            "/games/secure_game/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
            headers={"X-Admin-Key": "wrong-key"},
        )
        assert res_bad_key.status_code == 401

        # 3. Request with valid X-Admin-Key header succeeds (200)
        res_ok_header = client.post(
            "/games/secure_game/start",
            json={
                "mode": "progressive_rows",
                "ball_set": 75,
                "stage": 1,
                "access_policy": "PUBLIC",
            },
            headers={"X-Admin-Key": secret},
        )
        assert res_ok_header.status_code == 200

        # 4. Request with valid Bearer token succeeds (200)
        res_ok_bearer = client.post(
            "/games/secure_game/draw",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert res_ok_bearer.status_code == 200

        # 5. Public read endpoints remain open without auth
        res_state = client.get("/games/secure_game/state")
        assert res_state.status_code == 200

        res_validate = client.post(
            "/validate",
            json={"game_id": "secure_game", "serial": "NONEXIST"},
        )
        assert res_validate.status_code == 200

    @pytest.mark.asyncio
    async def test_production_bootstrap_fails_closed_without_credentials(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("ADMIN_API_KEY", raising=False)
        monkeypatch.delenv("ADMIN_SECRET", raising=False)

        assert allow_open_bootstrap() is False
        with pytest.raises(HTTPException) as admin_error:
            await verify_admin_flexible(x_admin_key=None, authorization=None, user=None)
        assert admin_error.value.status_code == 401

        class EmptyDatabase:
            async def execute(self, _statement):
                class Result:
                    @staticmethod
                    def scalar_one():
                        return 0

                return Result()

        with pytest.raises(HTTPException) as operator_error:
            await require_operator_with_bootstrap(
                user=None,
                db_session=EmptyDatabase(),
                x_admin_key=None,
                authorization=None,
            )
        assert operator_error.value.status_code == 401

    def test_production_cors_requires_explicit_non_wildcard_origins(self, monkeypatch):
        from app import get_cors_origins

        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
            get_cors_origins()

        monkeypatch.setenv("CORS_ORIGINS", "*")
        with pytest.raises(RuntimeError, match="Wildcard"):
            get_cors_origins()


class TestWebSocketConnectionLimits:
    @pytest.mark.asyncio
    async def test_concurrent_connections_cannot_exceed_limits(self):
        manager = ConnectionManager(
            max_connections_per_game=1,
            max_total_connections=1,
        )

        class FakeWebSocket:
            async def accept(self):
                await asyncio.sleep(0)

        sockets = [FakeWebSocket(), FakeWebSocket()]
        results = await asyncio.gather(
            *(manager.connect("limited_game", socket) for socket in sockets)
        )

        assert results.count(True) == 1
        assert results.count(False) == 1
        assert manager.total_connections == 1


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

        # "Backend process 1": generate and store a PERSISTENT card.
        first_instance = MemoryDB(card_db_path=db_path)
        grid = generate_75_ball_card()
        serial = serialize_card(grid)
        public_id = short_id(serial)
        first_instance.set_card(
            public_id,
            {"serial": serial, "game_id": "night_1", "grid": grid},
            persistent=True,
        )
        first_instance.close()  # simulates the backend process exiting

        # "Backend process 2": a brand new MemoryDB pointed at the same
        # file must see the card without ever being told about it again.
        second_instance = MemoryDB(card_db_path=db_path)
        assert public_id in second_instance.cards
        assert second_instance.cards[public_id]["serial"] == serial
        assert second_instance.cards[public_id]["grid"] == grid
        second_instance.close()

    def test_non_persistent_card_does_not_survive_restart(self, tmp_path):
        """Regression: the default (persistent=False) must remain
        ephemeral - a card generated without opting into persistence must
        NOT reappear in a fresh MemoryDB instance."""
        db_path = str(tmp_path / "cards.db")

        first_instance = MemoryDB(card_db_path=db_path)
        grid = generate_75_ball_card()
        serial = serialize_card(grid)
        public_id = short_id(serial)
        first_instance.set_card(
            public_id, {"serial": serial, "game_id": "night_1", "grid": grid}
        )  # persistent defaults to False
        assert public_id in first_instance.cards  # available while running
        first_instance.close()

        second_instance = MemoryDB(card_db_path=db_path)
        assert public_id not in second_instance.cards
        second_instance.close()

    def test_persistent_capacity_refuses_new_writes_without_evicting(self, tmp_path):
        db_path = str(tmp_path / "cards.db")
        instance = MemoryDB(max_persistent_cards=2, card_db_path=db_path)
        for i in range(2):
            instance.set_card(
                f"card_{i}",
                {"serial": f"s_{i}", "game_id": None, "grid": []},
                persistent=True,
            )
        # A third persistent write past capacity must be refused outright
        # rather than silently evicting an existing durable card.
        with pytest.raises(PersistentStorageFullError):
            instance.set_card(
                "card_2",
                {"serial": "s_2", "game_id": None, "grid": []},
                persistent=True,
            )

        assert "card_0" in instance.cards
        assert "card_1" in instance.cards
        assert "card_2" not in instance.cards
        instance.close()

        reloaded = MemoryDB(card_db_path=db_path)
        assert "card_0" in reloaded.cards
        assert "card_1" in reloaded.cards
        assert "card_2" not in reloaded.cards
        reloaded.close()

    def test_persistent_storage_full_raises_clear_error(self, tmp_path):
        db_path = str(tmp_path / "cards.db")
        instance = MemoryDB(max_persistent_cards=1, card_db_path=db_path)
        instance.set_card(
            "card_a", {"serial": "s_a", "game_id": None, "grid": []}, persistent=True
        )
        with pytest.raises(PersistentStorageFullError):
            instance.set_card(
                "card_b",
                {"serial": "s_b", "game_id": None, "grid": []},
                persistent=True,
            )
        instance.close()

    def test_clear_also_clears_disk(self, tmp_path):
        db_path = str(tmp_path / "cards.db")
        instance = MemoryDB(card_db_path=db_path)
        instance.set_card(
            "card_x", {"serial": "s_x", "game_id": None, "grid": []}, persistent=True
        )
        instance.clear()
        instance.close()

        reloaded = MemoryDB(card_db_path=db_path)
        assert len(reloaded.cards) == 0
        reloaded.close()


class TestSelectableCardPersistence:
    """API-level coverage for the `persistent` flag on POST /cards/batch.

    Default (omitted or false) -> ephemeral/in-memory, cleared on restart.
    True -> written to the durable SQLite-backed store, survives restart,
    reusable across many games. See storage/db.py's CardRepository for
    the underlying implementation these exercise through the real API.
    """

    def test_default_omitted_field_is_ephemeral(self, client):
        """Existing clients that don't send `persistent` at all must keep
        getting today's default: in-memory only."""
        resp = client.post("/cards/batch", json={"count": 3, "game_id": "g1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["persistent"] is False
        for card in data["cards"]:
            assert card["persistent"] is False
            assert not db.cards.is_persistent(card["public_id"])

    def test_explicit_false_is_ephemeral(self, client):
        resp = client.post(
            "/cards/batch", json={"count": 1, "game_id": "g1", "persistent": False}
        )
        assert resp.status_code == 200
        card = resp.json()["cards"][0]
        assert card["persistent"] is False
        assert not db.cards.is_persistent(card["public_id"])

    def test_persistent_true_is_written_to_durable_store(self, client):
        resp = client.post(
            "/cards/batch", json={"count": 1, "game_id": "g1", "persistent": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["persistent"] is True
        card = data["cards"][0]
        assert card["persistent"] is True
        assert db.cards.is_persistent(card["public_id"])

        # Retrieve it again and confirm identity/content are unchanged.
        get_resp = client.get(f"/cards/{card['public_id']}")
        assert get_resp.status_code == 200
        fetched = get_resp.json()
        assert fetched["exists"] is True
        assert fetched["persistent"] is True
        assert fetched["public_id"] == card["public_id"]
        assert fetched["serial"] == card["serial"]
        assert fetched["grid"] == card["grid"]

    def test_invalid_persistent_value_rejected(self, client):
        resp = client.post(
            "/cards/batch",
            json={"count": 1, "game_id": "g1", "persistent": "yes-please"},
        )
        assert resp.status_code == 422

    def test_batch_mixes_correctly_by_request(self, client):
        """Two separate batch requests with different `persistent` values
        each land in the correct store."""
        ephemeral = client.post(
            "/cards/batch", json={"count": 5, "game_id": "g1", "persistent": False}
        ).json()
        persistent = client.post(
            "/cards/batch", json={"count": 5, "game_id": "g1", "persistent": True}
        ).json()

        for card in ephemeral["cards"]:
            assert not db.cards.is_persistent(card["public_id"])
        for card in persistent["cards"]:
            assert db.cards.is_persistent(card["public_id"])

    def test_persistent_card_reusable_in_another_game_after_restart(self, tmp_path):
        """End-to-end: a persistent card generated for one game, on one
        MemoryDB instance, is still retrievable and valid for a second,
        unrelated game after a simulated restart (fresh MemoryDB)."""
        db_path = str(tmp_path / "cards.db")
        first = MemoryDB(card_db_path=db_path)
        first.set_game(
            "night_1",
            {"drawn": [], "mode": "full_house", "stage": 1, "status": "active"},
        )

        grid = generate_75_ball_card()
        serial = serialize_card(grid)
        public_id = short_id(serial)
        first.set_card(
            public_id,
            {"serial": serial, "game_id": "night_1", "grid": grid},
            persistent=True,
        )
        first.close()

        second = MemoryDB(card_db_path=db_path)
        second.set_game(
            "night_2",
            {"drawn": [], "mode": "diagonals", "stage": 1, "status": "active"},
        )
        for row in grid:
            for num in row:
                if num != "FREE":
                    second.games["night_2"]["drawn"].append(num)

        from logic.validate import validate_card

        card = second.cards.get(public_id)
        assert card is not None
        valid, _details = validate_card(second.games["night_2"], card)
        assert valid is True
        second.close()

    def test_persistent_full_returns_409(self, client, monkeypatch):
        monkeypatch.setattr(db.cards, "max_persistent_cards", 0)
        resp = client.post(
            "/cards/batch", json={"count": 1, "game_id": "g1", "persistent": True}
        )
        assert resp.status_code == 409
        assert "capacity" in resp.json()["detail"].lower()


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


class TestResourceBoundEnvConfig:
    """MAX_GAMES / MAX_MEMORY_CARDS / MAX_PERSISTENT_CARDS parsing."""

    def test_int_env_parses_valid_value(self, monkeypatch):
        from storage.db import _int_env

        monkeypatch.setenv("SOME_LIMIT", "42")
        assert _int_env("SOME_LIMIT", 10) == 42

    def test_int_env_falls_back_on_missing(self, monkeypatch):
        from storage.db import _int_env

        monkeypatch.delenv("SOME_LIMIT", raising=False)
        assert _int_env("SOME_LIMIT", 10) == 10

    def test_int_env_falls_back_on_invalid(self, monkeypatch):
        from storage.db import _int_env

        monkeypatch.setenv("SOME_LIMIT", "not-a-number")
        assert _int_env("SOME_LIMIT", 10) == 10

    def test_int_env_falls_back_on_empty_string(self, monkeypatch):
        from storage.db import _int_env

        monkeypatch.setenv("SOME_LIMIT", "")
        assert _int_env("SOME_LIMIT", 10) == 10
