import os
import pytest
import pytest_asyncio
from app import app
from auth.rate_limit import auth_rate_limiter
from auth.session import SESSION_COOKIE_NAME
from database import Base, close_db, get_engine
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture(autouse=True)
async def reset_db_and_limiter():
    await auth_rate_limiter.reset()
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await close_db()



@pytest.mark.asyncio
class TestAuthAPI:
    async def test_first_user_becomes_admin_and_receives_cookie(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # First registration -> ADMIN
            resp = await client.post(
                "/auth/register",
                json={
                    "username": "admin_user",
                    "email": "admin@example.com",
                    "password": "SuperSecretAdminPassword123!",
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["username"] == "admin_user"
            assert data["role"] == "ADMIN"
            assert data["is_active"] is True
            assert SESSION_COOKIE_NAME in resp.cookies

            # Second registration -> USER
            resp2 = await client.post(
                "/auth/register",
                json={
                    "username": "regular_user",
                    "email": "regular@example.com",
                    "password": "RegularUserPassword123!",
                },
            )
            assert resp2.status_code == 201
            assert resp2.json()["role"] == "OPERATOR"

    async def test_duplicate_registration_fails(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/auth/register",
                json={
                    "username": "unique_user",
                    "email": "unique@example.com",
                    "password": "Password12345!",
                },
            )

            # Same username
            dup_user = await client.post(
                "/auth/register",
                json={
                    "username": "unique_user",
                    "email": "other@example.com",
                    "password": "Password12345!",
                },
            )
            assert dup_user.status_code == 409

            # Same email
            dup_email = await client.post(
                "/auth/register",
                json={
                    "username": "other_name",
                    "email": "unique@example.com",
                    "password": "Password12345!",
                },
            )
            assert dup_email.status_code == 409

    async def test_login_with_username_or_email_and_get_me(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Register user
            await client.post(
                "/auth/register",
                json={
                    "username": "login_test",
                    "email": "login_test@example.com",
                    "password": "MySecretLoginPassword123!",
                },
            )

            # Clear cookies from client
            client.cookies.clear()

            # Check /auth/me unauthenticated
            me_unauth = await client.get("/auth/me")
            assert me_unauth.status_code == 401

            # Login with username
            login_resp = await client.post(
                "/auth/login",
                json={
                    "username": "login_test",
                    "password": "MySecretLoginPassword123!",
                },
            )
            assert login_resp.status_code == 200
            assert SESSION_COOKIE_NAME in login_resp.cookies

            # Now /auth/me succeeds
            me_resp = await client.get("/auth/me")
            assert me_resp.status_code == 200
            assert me_resp.json()["username"] == "login_test"

            # Check /auth/status
            status_resp = await client.get("/auth/status")
            assert status_resp.status_code == 200
            assert status_resp.json()["authenticated"] is True

            # Clear cookies and login with email
            client.cookies.clear()
            login_email_resp = await client.post(
                "/auth/login",
                json={
                    "username": "login_test@example.com",
                    "password": "MySecretLoginPassword123!",
                },
            )
            assert login_email_resp.status_code == 200

    async def test_invalid_login_credentials(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/auth/register",
                json={
                    "username": "existing_user",
                    "email": "exist@example.com",
                    "password": "ValidPassword123!",
                },
            )

            # Wrong password
            resp_wrong = await client.post(
                "/auth/login",
                json={
                    "username": "existing_user",
                    "password": "IncorrectPassword123!",
                },
            )
            assert resp_wrong.status_code == 401
            assert resp_wrong.json()["detail"] == "Invalid credentials"

            # Non-existent user
            resp_no_user = await client.post(
                "/auth/login",
                json={
                    "username": "non_existent_user",
                    "password": "IncorrectPassword123!",
                },
            )
            assert resp_no_user.status_code == 401
            assert resp_no_user.json()["detail"] == "Invalid credentials"

    async def test_logout_and_session_revocation(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/auth/register",
                json={
                    "username": "logout_user",
                    "email": "logout@example.com",
                    "password": "ValidPassword123!",
                },
            )

            # Verify authenticated
            assert (await client.get("/auth/me")).status_code == 200

            # Logout
            logout_resp = await client.post("/auth/logout")
            assert logout_resp.status_code == 200

            # Verify no longer authenticated
            assert (await client.get("/auth/me")).status_code == 401

    async def test_password_change_flow(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/auth/register",
                json={
                    "username": "pwd_user",
                    "email": "pwd@example.com",
                    "password": "OldPassword12345!",
                },
            )

            # Change password with wrong current password
            fail_resp = await client.post(
                "/auth/password",
                json={
                    "current_password": "WrongCurrentPassword123!",
                    "new_password": "NewSecretPassword12345!",
                },
            )
            assert fail_resp.status_code == 401

            # Change password with valid current password
            success_resp = await client.post(
                "/auth/password",
                json={
                    "current_password": "OldPassword12345!",
                    "new_password": "NewSecretPassword12345!",
                },
            )
            assert success_resp.status_code == 200

            # Login with old password fails
            client.cookies.clear()
            old_login = await client.post(
                "/auth/login",
                json={
                    "username": "pwd_user",
                    "password": "OldPassword12345!",
                },
            )
            assert old_login.status_code == 401

            # Login with new password succeeds
            new_login = await client.post(
                "/auth/login",
                json={
                    "username": "pwd_user",
                    "password": "NewSecretPassword12345!",
                },
            )
            assert new_login.status_code == 200

    async def test_security_headers_present(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/auth/status")
            assert resp.headers.get("X-Content-Type-Options") == "nosniff"
            assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
            assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
            assert "Content-Security-Policy" in resp.headers
