import hashlib
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from auth.session import (
    SESSION_COOKIE_NAME,
    cleanup_expired_sessions,
    clear_session_cookie,
    create_session,
    generate_session_token,
    get_session_user,
    hash_session_token,
    revoke_all_user_sessions,
    revoke_session,
    set_session_cookie,
)
from database import Base, close_db, get_engine, get_sessionmaker
from db_models import User, UserSession
from fastapi import Response


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await close_db()




@pytest.mark.asyncio
class TestServerSideSessions:
    async def test_session_token_entropy_and_hashing(self):
        token1 = generate_session_token()
        token2 = generate_session_token()

        assert token1 != token2
        assert len(token1) >= 43  # 32 bytes in urlsafe base64 is 43 chars (>256 bits)

        h1 = hash_session_token(token1)
        h2 = hash_session_token(token2)
        assert len(h1) == 64  # SHA-256 hex digest
        assert h1 == hashlib.sha256(token1.encode()).hexdigest()
        assert h1 != h2

    async def test_session_lifecycle(self):
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            user = User(
                username="sessionuser",
                email="session@example.com",
                role="USER",
                is_active=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

            # 1. Create session
            raw_token = await create_session(db, user.id, ip_address="1.2.3.4", user_agent="PyTestClient")
            assert raw_token is not None

            # 2. Validate session returns user
            fetched_user = await get_session_user(db, raw_token)
            assert fetched_user is not None
            assert fetched_user.id == user.id
            assert fetched_user.username == "sessionuser"

            # 3. Revoke session
            revoked = await revoke_session(db, raw_token)
            assert revoked is True

            # 4. Validating revoked session returns None
            assert await get_session_user(db, raw_token) is None

    async def test_revoke_all_user_sessions(self):
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            user = User(
                username="multiuser",
                email="multi@example.com",
                role="USER",
                is_active=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

            # Create 3 sessions
            tokens = [await create_session(db, user.id) for _ in range(3)]
            for t in tokens:
                assert await get_session_user(db, t) is not None

            # Revoke all
            count = await revoke_all_user_sessions(db, user.id)
            assert count == 3

            # All tokens are now invalid
            for t in tokens:
                assert await get_session_user(db, t) is None

    async def test_expired_session_is_rejected_and_cleaned(self):
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            user = User(
                username="expuser",
                email="exp@example.com",
                role="USER",
                is_active=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

            raw_token = generate_session_token()
            token_hash = hash_session_token(raw_token)
            past_time = datetime.now(timezone.utc) - timedelta(hours=2)

            expired_session = UserSession(
                user_id=user.id,
                session_token_hash=token_hash,
                expires_at=past_time,
            )
            db.add(expired_session)
            await db.commit()

            # get_session_user detects expired session and returns None
            assert await get_session_user(db, raw_token) is None

    async def test_disabled_user_session_is_rejected(self):
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            user = User(
                username="disableduser",
                email="disabled@example.com",
                role="USER",
                is_active=False,  # Account disabled
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

            raw_token = await create_session(db, user.id)
            assert await get_session_user(db, raw_token) is None

    async def test_cookie_helpers(self):
        resp = Response()
        set_session_cookie(resp, "test_token_12345")
        cookies = resp.headers.getlist("set-cookie")
        assert any(SESSION_COOKIE_NAME in c and "HttpOnly" in c for c in cookies)

        clear_resp = Response()
        clear_session_cookie(clear_resp)
        clear_cookies = clear_resp.headers.getlist("set-cookie")
        assert any(SESSION_COOKIE_NAME in c for c in clear_cookies)


