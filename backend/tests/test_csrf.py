import pytest
from auth.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    generate_csrf_token,
    set_csrf_cookie,
    verify_csrf_token,
)
from fastapi import HTTPException, Request, Response


@pytest.mark.asyncio
class TestCSRFProtection:
    async def test_safe_methods_bypass_csrf(self):
        # GET and OPTIONS do not require CSRF
        scope_get = {"type": "http", "method": "GET", "headers": []}
        req_get = Request(scope_get)
        await verify_csrf_token(req_get)

        scope_opt = {"type": "http", "method": "OPTIONS", "headers": []}
        req_opt = Request(scope_opt)
        await verify_csrf_token(req_opt)

    async def test_unauthenticated_request_bypasses_csrf(self):
        # Requests without ambient session cookies bypass CSRF check
        scope = {"type": "http", "method": "POST", "headers": []}
        req = Request(scope)
        await verify_csrf_token(req)

    async def test_cookie_auth_requires_csrf_defense(self):
        # Request has session cookie but no CSRF header/token
        headers = [(b"cookie", b"bingo_session=some_session_token")]
        scope = {"type": "http", "method": "POST", "headers": headers}
        req = Request(scope)

        with pytest.raises(HTTPException) as exc_info:
            await verify_csrf_token(req)
        assert exc_info.value.status_code == 403

    async def test_valid_csrf_token_header_passes(self):
        token = generate_csrf_token()
        headers = [
            (b"cookie", f"bingo_session=sess123; {CSRF_COOKIE_NAME}={token}".encode()),
            (CSRF_HEADER_NAME.lower().encode(), token.encode()),
        ]
        scope = {"type": "http", "method": "POST", "headers": headers}
        req = Request(scope)

        await verify_csrf_token(req)

    async def test_custom_requested_with_header_passes(self):
        headers = [
            (b"cookie", b"bingo_session=sess123"),
            (b"x-requested-with", b"XMLHttpRequest"),
        ]
        scope = {"type": "http", "method": "POST", "headers": headers}
        req = Request(scope)

        await verify_csrf_token(req)
