"""
Tests for Phase 2: RBAC & Resource Ownership.

Covers:
- Role hierarchy and permission checks
- Resource ownership (admin vs operator)
- User quota enforcement (active games, persistent cards)
- Admin user management endpoints
- User self-service endpoints (/auth/my/games, /auth/quota)
"""

import os

import pytest
import pytest_asyncio
from app import app
from auth.rate_limit import auth_rate_limiter
from auth.session import SESSION_COOKIE_NAME
from database import Base, close_db, get_engine
from httpx import ASGITransport, AsyncClient
from storage.db import db


@pytest_asyncio.fixture(autouse=True)
async def reset_db_and_limiter():
    await auth_rate_limiter.reset()
    db.clear()
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await close_db()
    db.clear()


async def _register_user(client, username, email, password="SuperSecretPassword123!"):
    """Helper to register a user and return the response."""
    resp = await client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    return resp


async def _login_user(client, username, password="SuperSecretPassword123!"):
    """Helper to login and return the response."""
    resp = await client.post(
        "/auth/login",
        json={"username": username, "password": password},
    )
    return resp


class TestRBACRoleHierarchy:
    """Test the role hierarchy and permission system."""

    @pytest.mark.asyncio
    async def test_first_user_is_admin(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await _register_user(client, "admin1", "admin1@test.com")
            assert resp.status_code == 201
            assert resp.json()["role"] == "ADMIN"

    @pytest.mark.asyncio
    async def test_second_user_is_regular(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_user(client, "admin1", "admin1@test.com")
            resp = await _register_user(client, "user1", "user1@test.com")
            assert resp.status_code == 201
            assert resp.json()["role"] == "USER"

    @pytest.mark.asyncio
    async def test_user_cannot_access_admin_endpoints(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create admin + regular user
            await _register_user(client, "admin1", "admin1@test.com")
            await _register_user(client, "user1", "user1@test.com")
            await client.post("/auth/logout")

            # Login as regular user
            resp = await _login_user(client, "user1")
            assert resp.status_code == 200

            # Try to list users
            resp = await client.get("/auth/admin/users")
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_list_users(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_user(client, "admin1", "admin1@test.com")
            await _register_user(client, "user1", "user1@test.com")

            resp = await client.get("/auth/admin/users")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 2


class TestResourceOwnership:
    """Test that operators can only access their own resources."""

    @pytest.mark.asyncio
    async def test_operator_cannot_access_other_users_game(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create admin + 2 users
            await _register_user(client, "admin1", "admin1@test.com")
            await _register_user(client, "user1", "user1@test.com")
            await _register_user(client, "user2", "user2@test.com")

            # Promote user1 to OPERATOR via admin
            # First, get user list to find user1's ID
            users = (await client.get("/auth/admin/users")).json()
            user1_id = [u for u in users if u["username"] == "user1"][0]["id"]
            await client.patch(
                f"/auth/admin/users/{user1_id}",
                json={"role": "OPERATOR"},
            )

            # Login as user1 and create a game
            await client.post("/auth/logout")
            await _login_user(client, "user1")
            resp = await client.post(
                "/games/game1/start",
                json={"mode": "regular", "ball_set": 75, "stage": 1},
            )
            assert resp.status_code == 200

            # Login as user2 and try to access game1
            await client.post("/auth/logout")
            await _login_user(client, "user2")
            resp = await client.post("/games/game1/draw")
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_access_any_game(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create admin + user
            await _register_user(client, "admin1", "admin1@test.com")
            await _register_user(client, "user1", "user1@test.com")

            # Promote user1 to OPERATOR
            users = (await client.get("/auth/admin/users")).json()
            user1_id = [u for u in users if u["username"] == "user1"][0]["id"]
            await client.patch(
                f"/auth/admin/users/{user1_id}",
                json={"role": "OPERATOR"},
            )

            # Login as user1 and create a game
            await client.post("/auth/logout")
            await _login_user(client, "user1")
            await client.post(
                "/games/game1/start",
                json={"mode": "regular", "ball_set": 75, "stage": 1},
            )

            # Login as admin and access the game
            await client.post("/auth/logout")
            await _login_user(client, "admin1")
            resp = await client.post("/games/game1/draw")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_operator_sees_own_cards_only(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Setup: admin + 2 operators
            await _register_user(client, "admin1", "admin1@test.com")
            await _register_user(client, "op1", "op1@test.com")
            await _register_user(client, "op2", "op2@test.com")

            users = (await client.get("/auth/admin/users")).json()
            op1_id = [u for u in users if u["username"] == "op1"][0]["id"]
            op2_id = [u for u in users if u["username"] == "op2"][0]["id"]
            await client.patch(f"/auth/admin/users/{op1_id}", json={"role": "OPERATOR"})
            await client.patch(f"/auth/admin/users/{op2_id}", json={"role": "OPERATOR"})

            # Op1 creates cards in game1
            await client.post("/auth/logout")
            await _login_user(client, "op1")
            await client.post("/games/game1/start", json={"mode": "regular", "ball_set": 75, "stage": 1})
            resp = await client.post("/cards/batch", json={"count": 3, "game_id": "game1"})
            assert resp.status_code == 200

            # Op2 creates cards in game1 too
            await client.post("/auth/logout")
            await _login_user(client, "op2")
            await client.post("/games/game1/start", json={"mode": "regular", "ball_set": 75, "stage": 1})
            resp = await client.post("/cards/batch", json={"count": 2, "game_id": "game1"})
            assert resp.status_code == 200

            # Op1 sees only own cards
            await client.post("/auth/logout")
            await _login_user(client, "op1")
            resp = await client.get("/games/game1/cards")
            assert resp.status_code == 200
            assert resp.json()["count"] == 3

            # Admin sees all cards
            await client.post("/auth/logout")
            await _login_user(client, "admin1")
            resp = await client.get("/games/game1/cards")
            assert resp.status_code == 200
            assert resp.json()["count"] == 5


class TestUserQuotas:
    """Test quota enforcement for active games and persistent cards."""

    @pytest.mark.asyncio
    async def test_active_games_quota_enforced(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create admin + operator
            await _register_user(client, "admin1", "admin1@test.com")
            await _register_user(client, "op1", "op1@test.com")
            users = (await client.get("/auth/admin/users")).json()
            op1_id = [u for u in users if u["username"] == "op1"][0]["id"]
            await client.patch(f"/auth/admin/users/{op1_id}", json={"role": "OPERATOR"})

            # Login as op1
            await client.post("/auth/logout")
            await _login_user(client, "op1")

            # Create max allowed games (default 10)
            for i in range(10):
                resp = await client.post(
                    f"/games/game{i}/start",
                    json={"mode": "regular", "ball_set": 75, "stage": 1},
                )
                assert resp.status_code == 200

            # Next game should be rejected
            resp = await client.post(
                "/games/game_overflow/start",
                json={"mode": "regular", "ball_set": 75, "stage": 1},
            )
            assert resp.status_code == 429
            assert "Quota exceeded" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_admin_exempt_from_game_quota(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_user(client, "admin1", "admin1@test.com")

            # Create 11 games as admin (should all succeed)
            for i in range(11):
                resp = await client.post(
                    f"/games/game{i}/start",
                    json={"mode": "regular", "ball_set": 75, "stage": 1},
                )
                assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_persistent_cards_quota_enforced(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create admin + operator
            await _register_user(client, "admin1", "admin1@test.com")
            await _register_user(client, "op1", "op1@test.com")
            users = (await client.get("/auth/admin/users")).json()
            op1_id = [u for u in users if u["username"] == "op1"][0]["id"]
            await client.patch(f"/auth/admin/users/{op1_id}", json={"role": "OPERATOR"})

            # Login as op1
            await client.post("/auth/logout")
            await _login_user(client, "op1")

            # Create 1000 persistent cards (should succeed)
            for i in range(10):
                resp = await client.post(
                    "/cards/batch",
                    json={"count": 100, "persistent": True},
                )
                assert resp.status_code == 200

            # Next batch should be rejected (would exceed 1000)
            resp = await client.post(
                "/cards/batch",
                json={"count": 1, "persistent": True},
            )
            assert resp.status_code == 429
            assert "Quota exceeded" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_quota_info_endpoint(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_user(client, "admin1", "admin1@test.com")
            await _register_user(client, "op1", "op1@test.com")
            users = (await client.get("/auth/admin/users")).json()
            op1_id = [u for u in users if u["username"] == "op1"][0]["id"]
            await client.patch(f"/auth/admin/users/{op1_id}", json={"role": "OPERATOR"})

            await client.post("/auth/logout")
            await _login_user(client, "op1")

            # Create a game
            await client.post(
                "/games/game1/start",
                json={"mode": "regular", "ball_set": 75, "stage": 1},
            )

            # Check quota
            resp = await client.get("/auth/quota")
            assert resp.status_code == 200
            data = resp.json()
            assert data["active_games"] == 1
            assert data["persistent_cards"] == 0
            assert data["max_games"] == 10
            assert data["max_persistent_cards"] == 1000


class TestAdminUserManagement:
    """Test admin user management endpoints."""

    @pytest.mark.asyncio
    async def test_admin_can_promote_user_to_operator(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_user(client, "admin1", "admin1@test.com")
            await _register_user(client, "user1", "user1@test.com")

            users = (await client.get("/auth/admin/users")).json()
            user1_id = [u for u in users if u["username"] == "user1"][0]["id"]

            resp = await client.patch(
                f"/auth/admin/users/{user1_id}",
                json={"role": "OPERATOR"},
            )
            assert resp.status_code == 200
            assert resp.json()["role"] == "OPERATOR"

    @pytest.mark.asyncio
    async def test_admin_cannot_modify_self(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_user(client, "admin1", "admin1@test.com")

            users = (await client.get("/auth/admin/users")).json()
            admin_id = [u for u in users if u["username"] == "admin1"][0]["id"]

            resp = await client.patch(
                f"/auth/admin/users/{admin_id}",
                json={"role": "USER"},
            )
            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_admin_can_deactivate_user(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_user(client, "admin1", "admin1@test.com")
            await _register_user(client, "user1", "user1@test.com")

            users = (await client.get("/auth/admin/users")).json()
            user1_id = [u for u in users if u["username"] == "user1"][0]["id"]

            # Deactivate
            resp = await client.patch(
                f"/auth/admin/users/{user1_id}",
                json={"is_active": False},
            )
            assert resp.status_code == 200
            assert resp.json()["is_active"] is False

            # Try to login as deactivated user
            await client.post("/auth/logout")
            resp = await _login_user(client, "user1")
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_delete_user(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_user(client, "admin1", "admin1@test.com")
            await _register_user(client, "user1", "user1@test.com")

            users = (await client.get("/auth/admin/users")).json()
            user1_id = [u for u in users if u["username"] == "user1"][0]["id"]

            resp = await client.delete(f"/auth/admin/users/{user1_id}")
            assert resp.status_code == 200

            # User should no longer exist
            resp = await client.get(f"/auth/admin/users/{user1_id}")
            assert resp.status_code == 404


class TestUserServiceEndpoints:
    """Test user self-service endpoints."""

    @pytest.mark.asyncio
    async def test_my_games_endpoint(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_user(client, "admin1", "admin1@test.com")
            await _register_user(client, "op1", "op1@test.com")

            users = (await client.get("/auth/admin/users")).json()
            op1_id = [u for u in users if u["username"] == "op1"][0]["id"]
            await client.patch(f"/auth/admin/users/{op1_id}", json={"role": "OPERATOR"})

            await client.post("/auth/logout")
            await _login_user(client, "op1")

            # Create games
            for i in range(3):
                await client.post(
                    f"/games/mygame{i}/start",
                    json={"mode": "regular", "ball_set": 75, "stage": 1},
                )

            resp = await client.get("/auth/my/games")
            assert resp.status_code == 200
            assert resp.json()["count"] == 3

    @pytest.mark.asyncio
    async def test_delete_own_game(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_user(client, "admin1", "admin1@test.com")
            await _register_user(client, "op1", "op1@test.com")

            users = (await client.get("/auth/admin/users")).json()
            op1_id = [u for u in users if u["username"] == "op1"][0]["id"]
            await client.patch(f"/auth/admin/users/{op1_id}", json={"role": "OPERATOR"})

            await client.post("/auth/logout")
            await _login_user(client, "op1")

            await client.post(
                "/games/game1/start",
                json={"mode": "regular", "ball_set": 75, "stage": 1},
            )

            resp = await client.delete("/auth/my/games/game1")
            assert resp.status_code == 200

            # Verify it's gone
            resp = await client.get("/auth/my/games")
            assert resp.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_user_cannot_delete_others_game(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_user(client, "admin1", "admin1@test.com")
            await _register_user(client, "op1", "op1@test.com")
            await _register_user(client, "op2", "op2@test.com")

            users = (await client.get("/auth/admin/users")).json()
            op1_id = [u for u in users if u["username"] == "op1"][0]["id"]
            op2_id = [u for u in users if u["username"] == "op2"][0]["id"]
            await client.patch(f"/auth/admin/users/{op1_id}", json={"role": "OPERATOR"})
            await client.patch(f"/auth/admin/users/{op2_id}", json={"role": "OPERATOR"})

            # Op1 creates game
            await client.post("/auth/logout")
            await _login_user(client, "op1")
            await client.post(
                "/games/game1/start",
                json={"mode": "regular", "ball_set": 75, "stage": 1},
            )

            # Op2 tries to delete it
            await client.post("/auth/logout")
            await _login_user(client, "op2")
            resp = await client.delete("/auth/my/games/game1")
            assert resp.status_code == 403


class TestOperatorRolePromotion:
    """Test that users can be promoted to OPERATOR and create resources."""

    @pytest.mark.asyncio
    async def test_promoted_operator_can_create_games(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_user(client, "admin1", "admin1@test.com")
            await _register_user(client, "user1", "user1@test.com")

            users = (await client.get("/auth/admin/users")).json()
            user1_id = [u for u in users if u["username"] == "user1"][0]["id"]

            # Promote to operator
            resp = await client.patch(
                f"/auth/admin/users/{user1_id}",
                json={"role": "OPERATOR"},
            )
            assert resp.status_code == 200

            # Re-login to get updated role
            await client.post("/auth/logout")
            await _login_user(client, "user1")

            # Create a game
            resp = await client.post(
                "/games/game1/start",
                json={"mode": "regular", "ball_set": 75, "stage": 1},
            )
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_regular_user_cannot_create_games(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _register_user(client, "admin1", "admin1@test.com")
            await _register_user(client, "user1", "user1@test.com")

            await client.post("/auth/logout")
            await _login_user(client, "user1")

            resp = await client.post(
                "/games/game1/start",
                json={"mode": "regular", "ball_set": 75, "stage": 1},
            )
            assert resp.status_code in (401, 403)
