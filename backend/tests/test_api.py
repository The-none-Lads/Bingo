import pytest
from app import app
from fastapi.testclient import TestClient
from logic.draws import DrawEngine
from storage.db import db


@pytest.fixture(autouse=True)
def clean_db():
    """Clean database before each test."""
    db.games.clear()
    db.cards.clear()
    db.max_concurrent_games = max(1, min(db.max_games, 100))
    db.inactivity_timeout_minutes = 45
    db.save_settings()
    yield
    db.games.clear()
    db.cards.clear()
    db.max_concurrent_games = max(1, min(db.max_games, 100))
    db.inactivity_timeout_minutes = 45
    db.save_settings()


@pytest.fixture
def client():
    """Create test client."""
    with TestClient(app) as test_client:
        yield test_client


class TestGameEndpoints:
    """Test game management endpoints."""

    def test_start_game(self, client):
        """
        Test starting a new game returns the expected message and config.
        """
        response = client.post(
            "/games/test_game/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
        )

        assert response.status_code == 200
        data = response.json()

        # The API should return a message and a config object
        assert "message" in data
        assert data["message"] == "Game test_game started"

        assert "config" in data
        config = data["config"]

        # Verify config matches what we sent (or defaults if omitted)
        assert config["mode"] == "progressive_rows"
        assert config["ball_set"] == 75
        assert config["stage"] == 1

    def test_generate_multiple_cards(self, client):
        """Test generating multiple cards."""
        response = client.post(
            "/cards/batch", json={"count": 50, "game_id": "test_game"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 50
        assert len(data["cards"]) == 50

        # All cards should have unique IDs
        ids = [card["public_id"] for card in data["cards"]]
        assert len(set(ids)) == 50

    def test_generate_cards_default_count(self, client):
        response = client.post(
            "/cards/batch",
            json={"count": 50, "game_id": "test_game"},  # must provide explicitly now
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 50

    def test_get_card_by_id(self, client):
        """Test retrieving a card by public ID."""
        # Generate a card first
        gen_response = client.post(
            "/cards/batch", json={"count": 1, "game_id": "test_game"}
        )
        card_id = gen_response.json()["cards"][0]["public_id"]

        # Retrieve it
        response = client.get(f"/cards/{card_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is True
        assert data["public_id"] == card_id
        assert len(data["grid"]) == 5
        assert data["grid"][2][2] == "FREE"

    def test_get_nonexistent_card(self, client):
        """Test retrieving a non-existent card."""
        response = client.get("/cards/NOTEXIST")

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is False
        assert data["public_id"] == "NOTEXIST"
        assert data["grid"] == []

    def test_card_grid_structure(self, client):
        """Test that generated cards have correct structure."""
        response = client.post(
            "/cards/batch", json={"count": 1, "game_id": "test_game"}
        )

        grid = response.json()["cards"][0]["grid"]

        # Check 5x5 structure
        assert len(grid) == 5
        for row in grid:
            assert len(row) == 5

        # Check FREE space
        assert grid[2][2] == "FREE"

        # Check column ranges (roughly)
        for col_idx in range(5):
            col_vals = [
                grid[row][col_idx] for row in range(5) if grid[row][col_idx] != "FREE"
            ]
            for val in col_vals:
                assert isinstance(val, int)


class TestValidationEndpoint:
    """Test card validation endpoint."""

    def test_validate_winning_card_one_row(self, client):
        """Test validating a winning card (1 row)."""
        # Start game
        client.post(
            "/games/test_game/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
        )

        # Generate a card
        gen_response = client.post(
            "/cards/batch", json={"count": 1, "game_id": "test_game"}
        )
        card = gen_response.json()["cards"][0]
        card_id = card["public_id"]

        # Draw all numbers from first row
        first_row = [num for num in card["grid"][0] if num != "FREE"]
        for num in first_row:
            # Manually add to drawn list (hack for testing)
            db.games["test_game"]["drawn"].append(num)

        # Validate
        response = client.post(
            "/validate", json={"game_id": "test_game", "serial": card_id}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["public_id"] == card_id

    def test_validate_non_winning_card(self, client):
        """Test validating a non-winning card."""
        # Start game
        client.post(
            "/games/test_game/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
        )

        # Generate a card
        gen_response = client.post(
            "/cards/batch", json={"count": 1, "game_id": "test_game"}
        )
        card_id = gen_response.json()["cards"][0]["public_id"]

        # Draw only 2 numbers
        client.post("/games/test_game/draw")
        client.post("/games/test_game/draw")

        # Validate
        response = client.post(
            "/validate", json={"game_id": "test_game", "serial": card_id}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False

    def test_validate_nonexistent_card(self, client):
        """Test validating a non-existent card."""
        client.post(
            "/games/test_game/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
        )

        response = client.post(
            "/validate", json={"game_id": "test_game", "serial": "BADCARD1"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "error" in data["details"]
        assert data["grid"] == []

    def test_validate_nonexistent_game(self, client):
        """Test validating against non-existent game."""
        response = client.post(
            "/validate", json={"game_id": "nonexistent", "serial": "CARD1234"}
        )

        assert response.status_code == 404

    def test_validate_full_house(self, client):
        """Test validating full house win."""
        # Start game in full house mode
        client.post(
            "/games/test_game/start",
            json={"mode": "full_house", "ball_set": 75, "stage": 1},
        )

        # Generate a card
        gen_response = client.post(
            "/cards/batch", json={"count": 1, "game_id": "test_game"}
        )
        card = gen_response.json()["cards"][0]
        card_id = card["public_id"]

        # Draw all numbers on the card
        for row in card["grid"]:
            for num in row:
                if num != "FREE":
                    db.games["test_game"]["drawn"].append(num)

        # Validate
        response = client.post(
            "/validate", json={"game_id": "test_game", "serial": card_id}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True


class TestAdminGameLifecycle:
    def test_stop_game_requires_admin_and_releases_capacity(self):
        db.games.clear()
        db.max_concurrent_games = 1
        db.save_settings()

        with TestClient(
            app,
            headers={"X-Requested-With": "XMLHttpRequest"},
        ) as client:
            register = client.post(
                "/auth/register",
                json={"username": "adminstop", "email": "adminstop@test.com", "password": "SuperSecretPassword123!"},
            )
            assert register.status_code == 201

            login = client.post(
                "/auth/login",
                json={"username": "adminstop", "password": "SuperSecretPassword123!"},
            )
            assert login.status_code == 200

            start = client.post(
                "/games/stop_game/start",
                json={"mode": "regular", "ball_set": 75, "stage": 1, "access_policy": "PUBLIC"},
            )
            assert start.status_code == 200

            stop = client.post("/admin/games/stop_game/stop")
            assert stop.status_code == 200
            assert stop.json()["message"] == "Game stop_game stopped"

            state = client.get("/games/stop_game/state")
            assert state.status_code == 404
            assert "stop_game" not in db.games

            second = client.post(
                "/games/stop_game/start",
                json={"mode": "regular", "ball_set": 75, "stage": 1, "access_policy": "PUBLIC"},
            )
            assert second.status_code == 200

    def test_max_concurrent_games_blocks_new_games(self):
        db.games.clear()
        db.max_concurrent_games = 1
        db.save_settings()

        with TestClient(app) as client:
            client.post(
                "/games/first/start",
                json={"mode": "regular", "ball_set": 75, "stage": 1},
            )
            response = client.post(
                "/games/second/start",
                json={"mode": "regular", "ball_set": 75, "stage": 1},
            )
            assert response.status_code == 409
            assert "Concurrent game limit reached" in response.json()["detail"]

    def test_reusing_closed_game_id_still_obeys_concurrent_limit(self, client):
        db.max_concurrent_games = 1
        db.set_game("active_game", {"status": "active", "drawn": []})
        db.set_game("closed_game", {"status": "expired", "drawn": []})

        response = client.post(
            "/games/closed_game/start",
            json={"mode": "regular", "ball_set": 75, "stage": 1},
        )

        assert response.status_code == 409
        assert "Concurrent game limit reached" in response.json()["detail"]

    def test_inactivity_expiration_marks_game_expired(self):
        db.games.clear()
        db.max_concurrent_games = 2
        db.inactivity_timeout_minutes = 30
        db.save_settings()

        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        old = (now - __import__("datetime").timedelta(minutes=31)).isoformat()
        db.set_game(
            "idle_game",
            {
                "engine": DrawEngine(max_number=75),
                "drawn": [],
                "mode": "regular",
                "stage": 1,
                "ball_set": 75,
                "status": "active",
                "last_activity_at": old,
            },
        )

        expired = db.expire_inactive_games(now=now)
        assert expired == ["idle_game"]
        assert "idle_game" not in db.games
        assert db.count_active_games() == 0

    def test_expired_game_can_be_restarted_with_same_id(self, client):
        db.inactivity_timeout_minutes = 30
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        old = (now - __import__("datetime").timedelta(minutes=31)).isoformat()
        db.set_game(
            "idle_game",
            {
                "engine": DrawEngine(max_number=75),
                "drawn": [1, 2, 3],
                "mode": "regular",
                "stage": 1,
                "ball_set": 75,
                "status": "active",
                "last_activity_at": old,
            },
        )

        assert db.expire_inactive_games(now=now) == ["idle_game"]
        response = client.post(
            "/games/idle_game/start",
            json={"mode": "regular", "ball_set": 75, "stage": 1, "access_policy": "PUBLIC"},
        )

        assert response.status_code == 200
        assert db.games["idle_game"]["status"] == "active"
        assert db.games["idle_game"]["drawn"] == []


class TestCORS:
    """Test CORS configuration."""

    def test_cors_headers_present(self, client):
        """Test that CORS headers are present in responses."""
        response = client.options(
            "/games/test/state",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert "access-control-allow-origin" in response.headers


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_complete_game_workflow(self, client):
        """Test a complete game from start to win."""
        game_id = "integration_test"

        # 1. Start game
        start_response = client.post(
            f"/games/{game_id}/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
        )
        assert start_response.status_code == 200

        # 2. Generate cards
        cards_response = client.post(
            "/cards/batch", json={"count": 10, "game_id": game_id}
        )
        assert cards_response.status_code == 200
        cards = cards_response.json()["cards"]
        test_card = cards[0]

        # 3. Draw numbers until first row is complete
        first_row = [num for num in test_card["grid"][0] if num != "FREE"]
        for num in first_row:
            db.games[game_id]["drawn"].append(num)

        # 4. Check game state
        state_response = client.get(f"/games/{game_id}/state")
        assert state_response.status_code == 200
        state = state_response.json()
        assert len(state["drawn"]) >= 5

        # 5. Validate winning card
        validate_response = client.post(
            "/validate", json={"game_id": game_id, "serial": test_card["public_id"]}
        )
        assert validate_response.status_code == 200
        result = validate_response.json()
        assert result["valid"] is True

    def test_progressive_game_stages(self, client):
        """Test progressive stages in a game."""
        game_id = "progressive_test"

        # Start game
        client.post(
            f"/games/{game_id}/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
        )

        # Advance to stage 2
        response = client.post(f"/games/{game_id}/stage/2")
        assert response.status_code == 200

        # Advance to stage 3
        response = client.post(f"/games/{game_id}/stage/3")
        assert response.status_code == 200

        # Verify final stage
        state = client.get(f"/games/{game_id}/state").json()
        assert state["stage"] == 3

    def test_multiple_games_simultaneously(self, client):
        """Test running multiple games at once."""
        # Start three different games
        for i in range(3):
            response = client.post(
                f"/games/game_{i}/start",
                json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
            )
            assert response.status_code == 200

        # Verify all games exist independently
        for i in range(3):
            response = client.get(f"/games/game_{i}/state")
            assert response.status_code == 200
            assert response.json()["game_id"] == f"game_{i}"


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_game_id_format(self, client):
        """Test handling of various game ID formats."""
        # Should all work (no validation on game_id format)
        valid_ids = ["test", "test-123", "test_game", "CAPS", "123"]

        for game_id in valid_ids:
            response = client.post(
                f"/games/{game_id}/start",
                json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
            )
            assert response.status_code == 200

    def test_invalid_request_body(self, client):
        """Test handling of invalid request bodies."""
        response = client.post("/games/test/start", json={"invalid": "data"})
        # Should fail validation
        assert response.status_code == 422


class TestHealthEndpoint:
    def test_health_checks_database_connectivity(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestDrawEndpoints:
    def test_missing_required_fields(self, client):
        response = client.post("/cards/batch", json={})
        assert response.status_code == 422

    def test_start_game_different_modes(self, client):
        """Test starting games with different modes."""
        modes = ["progressive_rows", "full_house", "four_corners", "diagonals"]

        for mode in modes:
            response = client.post(
                f"/games/game_{mode}/start",
                json={"mode": mode, "ball_set": 75, "stage": 1},
            )
            assert response.status_code == 200
            assert response.json()["config"]["mode"] == mode

    def test_draw_number(self, client):
        """Test drawing a number."""
        # Start game first
        client.post(
            "/games/test_game/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
        )

        # Draw number
        response = client.post("/games/test_game/draw")

        assert response.status_code == 200
        data = response.json()
        assert "drawn_number" in data
        assert "all_drawn" in data
        assert 1 <= data["drawn_number"] <= 75
        assert len(data["all_drawn"]) == 1

    def test_draw_multiple_numbers(self, client):
        """Test drawing multiple numbers."""
        client.post(
            "/games/test_game/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
        )

        drawn_numbers = []
        for _ in range(10):
            response = client.post("/games/test_game/draw")
            assert response.status_code == 200
            drawn_numbers.append(response.json()["drawn_number"])

        # All should be unique
        assert len(set(drawn_numbers)) == 10

    def test_draw_number_game_not_found(self, client):
        """Test drawing from non-existent game."""
        response = client.post("/games/nonexistent/draw")
        assert response.status_code == 404

    def test_draw_all_numbers_exhaustion(self, client):
        """Test that drawing all numbers eventually returns error."""
        client.post(
            "/games/test_game/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
        )

        # Draw all 75 numbers
        for _ in range(75):
            response = client.post("/games/test_game/draw")
            assert response.status_code == 200

        # 76th draw should fail
        response = client.post("/games/test_game/draw")
        assert response.status_code == 400
        assert "No numbers left" in response.json()["detail"]

    def test_get_game_state(self, client):
        """Test getting game state."""
        client.post(
            "/games/test_game/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
        )

        response = client.get("/games/test_game/state")

        assert response.status_code == 200
        data = response.json()
        assert data["game_id"] == "test_game"
        assert data["mode"] == "progressive_rows"
        assert data["stage"] == 1
        assert data["status"] == "active"
        assert isinstance(data["drawn"], list)

    def test_get_game_state_not_found(self, client):
        """Test getting state of non-existent game."""
        response = client.get("/games/nonexistent/state")
        assert response.status_code == 404

    def test_set_stage(self, client):
        """Test changing game stage."""
        client.post(
            "/games/test_game/start",
            json={"mode": "progressive_rows", "ball_set": 75, "stage": 1},
        )

        response = client.post("/games/test_game/stage/3")

        assert response.status_code == 200
        data = response.json()
        assert data["game_id"] == "test_game"
        assert data["stage"] == 3

        # Verify in game state
        state = client.get("/games/test_game/state").json()
        assert state["stage"] == 3

    def test_set_stage_game_not_found(self, client):
        """Test setting stage for non-existent game."""
        response = client.post("/games/nonexistent/stage/2")
        assert response.status_code == 404

    class TestCardEndpoints:
        """Test card generation and retrieval endpoints."""

        def test_generate_single_card(self, client):
            """Test generating a single card."""
            response = client.post(
                "/cards/batch", json={"count": 1, "game_id": "test_game"}
            )

            assert response.status_code == 200
