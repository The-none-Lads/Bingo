"""
Tests for OIDC authentication module.

These tests mock the OIDC provider to test the flow without requiring
an actual IdP connection.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

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
    db.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class TestOIDCConfig:
    """Test OIDC configuration."""

    def test_oidc_disabled_by_default(self):
        from routes.oidc import is_oidc_enabled
        with patch.dict(os.environ, {}, clear=True):
            assert is_oidc_enabled() is False

    def test_oidc_enabled_via_env(self):
        from routes.oidc import is_oidc_enabled
        with patch.dict(os.environ, {"OIDC_ENABLED": "true"}):
            assert is_oidc_enabled() is True

    def test_oidc_config_from_env(self):
        from routes.oidc import get_oidc_config
        env = {
            "OIDC_ENABLED": "true",
            "OIDC_ISSUER": "https://auth.example.com",
            "OIDC_CLIENT_ID": "bingo-app",
            "OIDC_CLIENT_SECRET": "secret123",
            "OIDC_REDIRECT_URI": "https://bingo.example.com/auth/oidc/callback",
            "OIDC_SCOPES": "openid email profile groups",
            "OIDC_ADMIN_GROUPS": "bingo-admins,admins",
            "OIDC_OPERATOR_GROUPS": "bingo-operators,operators",
        }
        with patch.dict(os.environ, env):
            config = get_oidc_config()
            assert config["enabled"] is True
            assert config["issuer"] == "https://auth.example.com"
            assert config["client_id"] == "bingo-app"
            assert config["scopes"] == "openid email profile groups"
            assert "bingo-admins" in config["admin_groups"]
            assert "admins" in config["admin_groups"]

    @pytest.mark.asyncio
    async def test_status_endpoint_when_disabled(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/auth/oidc/status")
            data = response.json()
            assert data["enabled"] is False


class TestOIDCLoginFlow:
    """Test OIDC login flow with mocked provider."""

    @pytest.mark.asyncio
    async def test_login_redirects_when_oidc_disabled(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/auth/oidc/login")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_login_returns_authorization_url(self):
        discovery_doc = {
            "authorization_endpoint": "https://auth.example.com/authorize",
            "token_endpoint": "https://auth.example.com/token",
            "jwks_uri": "https://auth.example.com/jwks",
            "issuer": "https://auth.example.com",
        }

        with patch.dict(os.environ, {
            "OIDC_ENABLED": "true",
            "OIDC_ISSUER": "https://auth.example.com",
            "OIDC_CLIENT_ID": "test-client",
            "OIDC_CLIENT_SECRET": "test-secret",
            "OIDC_REDIRECT_URI": "http://localhost:8000/auth/oidc/callback",
        }):
            with patch("routes.oidc.discover_oidc_config", new_callable=AsyncMock) as mock_discover:
                mock_discover.return_value = discovery_doc

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as ac:
                    response = await ac.get("/auth/oidc/login")
                    assert response.status_code == 200
                    data = response.json()
                    assert "authorization_url" in data
                    assert "https://auth.example.com/authorize" in data["authorization_url"]
                    assert "client_id=test-client" in data["authorization_url"]
                    assert "state=" in data["authorization_url"]

    @pytest.mark.asyncio
    async def test_callback_rejects_invalid_state(self):
        with patch.dict(os.environ, {"OIDC_ENABLED": "true"}):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get(
                    "/auth/oidc/callback?code=test-code&state=invalid-state"
                )
                assert response.status_code == 400
                assert "Invalid or expired state" in response.json()["detail"]


class TestOIDCRoleMapping:
    """Test OIDC claim to role mapping."""

    def test_admin_group_maps_to_admin(self):
        from routes.oidc import map_oidc_claims_to_role
        config = {"role_claim": "groups", "admin_groups": ["bingo-admins"], "operator_groups": []}
        claims = {"groups": ["bingo-admins", "other-group"]}
        assert map_oidc_claims_to_role(claims, config) == "ADMIN"

    def test_operator_group_maps_to_operator(self):
        from routes.oidc import map_oidc_claims_to_role
        config = {"role_claim": "groups", "admin_groups": ["bingo-admins"], "operator_groups": ["bingo-operators"]}
        claims = {"groups": ["bingo-operators"]}
        assert map_oidc_claims_to_role(claims, config) == "OPERATOR"

    def test_no_matching_group_defaults_to_operator(self):
        from routes.oidc import map_oidc_claims_to_role
        config = {"role_claim": "groups", "admin_groups": ["bingo-admins"], "operator_groups": ["bingo-operators"]}
        claims = {"groups": ["some-other-group"]}
        assert map_oidc_claims_to_role(claims, config) == "OPERATOR"

    def test_single_string_group_claim(self):
        """Handle IdP that returns a single string instead of list."""
        from routes.oidc import map_oidc_claims_to_role
        config = {"role_claim": "groups", "admin_groups": ["bingo-admins"], "operator_groups": []}
        claims = {"groups": "bingo-admins"}
        assert map_oidc_claims_to_role(claims, config) == "ADMIN"


class TestOIDCTokenValidation:
    """Test ID token validation."""

    def test_valid_token_structure(self):
        import base64
        import json
        from routes.oidc import validate_id_token

        # Create a mock JWT (header.payload.signature)
        header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(json.dumps({
            "iss": "https://auth.example.com",
            "aud": "test-client",
            "sub": "user123",
            "email": "user@example.com",
            "exp": 9999999999,
        }).encode()).decode().rstrip("=")
        signature = "mock-signature"

        token = f"{header}.{payload}.{signature}"

        claims = validate_id_token(
            token=token,
            issuer="https://auth.example.com",
            client_id="test-client",
        )
        assert claims["sub"] == "user123"
        assert claims["email"] == "user@example.com"

    def test_invalid_issuer_rejected(self):
        from routes.oidc import validate_id_token
        import base64
        import json

        header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(json.dumps({
            "iss": "https://wrong-issuer.com",
            "aud": "test-client",
            "sub": "user123",
            "exp": 9999999999,
        }).encode()).decode().rstrip("=")
        token = f"{header}.{payload}.sig"

        with pytest.raises(Exception) as exc_info:
            validate_id_token(token, issuer="https://auth.example.com", client_id="test-client")
        assert "Invalid token issuer" in str(exc_info.value)

    def test_invalid_audience_rejected(self):
        from routes.oidc import validate_id_token
        import base64
        import json

        header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(json.dumps({
            "iss": "https://auth.example.com",
            "aud": "wrong-client",
            "sub": "user123",
            "exp": 9999999999,
        }).encode()).decode().rstrip("=")
        token = f"{header}.{payload}.sig"

        with pytest.raises(Exception) as exc_info:
            validate_id_token(token, issuer="https://auth.example.com", client_id="test-client")
        assert "Invalid token audience" in str(exc_info.value)

    def test_expired_token_rejected(self):
        from routes.oidc import validate_id_token
        import base64
        import json

        header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(json.dumps({
            "iss": "https://auth.example.com",
            "aud": "test-client",
            "sub": "user123",
            "exp": 1000000000,  # Expired in 2001
        }).encode()).decode().rstrip("=")
        token = f"{header}.{payload}.sig"

        with pytest.raises(Exception) as exc_info:
            validate_id_token(token, issuer="https://auth.example.com", client_id="test-client")
        assert "Token expired" in str(exc_info.value)


class TestOIDCAccountLinking:
    """Test OIDC account linking."""

    @pytest.mark.asyncio
    async def test_find_or_create_new_oidc_user(self):
        from routes.oidc import find_or_create_oidc_user
        from database import get_db_session

        db_session = await anext(get_db_session())

        user, created = await find_or_create_oidc_user(
            db=db_session,
            issuer="https://auth.example.com",
            subject="user123",
            email="newuser@example.com",
            name="New User",
        )

        assert created is True
        assert user.username == "New User"
        assert user.email == "newuser@example.com"
        assert user.role == "OPERATOR"

    @pytest.mark.asyncio
    async def test_find_existing_oidc_user(self):
        from routes.oidc import find_or_create_oidc_user
        from database import get_db_session

        db_session = await anext(get_db_session())

        # Create user first
        user1, created1 = await find_or_create_oidc_user(
            db=db_session,
            issuer="https://auth.example.com",
            subject="user456",
            email="existing@example.com",
        )

        # Find same user again
        user2, created2 = await find_or_create_oidc_user(
            db=db_session,
            issuer="https://auth.example.com",
            subject="user456",
            email="different@example.com",  # Email doesn't matter for lookup
        )

        assert created2 is False
        assert user1.id == user2.id


class TestStateManagement:
    """Test OIDC state parameter management."""

    def test_generate_and_validate_state(self):
        from routes.oidc import generate_state, validate_state

        state = generate_state()
        assert len(state) > 0

        # Valid state should pass
        assert validate_state(state) is True

        # Already consumed state should fail
        assert validate_state(state) is False

        # Unknown state should fail
        assert validate_state("unknown-state") is False


# Import patch at module level for tests that need it
from unittest.mock import patch
