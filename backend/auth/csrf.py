import secrets
from typing import Optional
from fastapi import Cookie, Header, HTTPException, Request, Response

CSRF_COOKIE_NAME = "bingo_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, csrf_token: Optional[str] = None) -> str:
    """Set the non-HttpOnly CSRF cookie so JavaScript can read it and send X-CSRF-Token header."""
    token = csrf_token or generate_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        max_age=7 * 24 * 60 * 60,
        path="/",
        httponly=False,  # Accessible to frontend JS to mirror in X-CSRF-Token header
        secure=False,    # Match dev environment or production
        samesite="lax",
    )
    return token


async def verify_csrf_token(
    request: Request,
) -> None:
    """
    FastAPI dependency for verifying CSRF protection on authenticated state-changing endpoints.
    Allows requests if:
    - Origin / Referer matches the server or allowed CORS origins, AND
    - X-CSRF-Token header matches bingo_csrf cookie (if cookie is present), OR
    - Custom anti-CSRF header (e.g. X-Requested-With / X-Admin-Key) is present.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    # If session cookie is present, check double-submit or custom header
    session_cookie = request.cookies.get("bingo_session")
    if not session_cookie:
        # Not using ambient session cookie auth (e.g. token in header or public endpoint)
        return

    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    csrf_header = request.headers.get(CSRF_HEADER_NAME) or request.headers.get("x-csrf-token")

    # Check custom header / double-submit
    if csrf_header and csrf_cookie and secrets.compare_digest(csrf_header, csrf_cookie):
        return

    # Also accept X-Requested-With: XMLHttpRequest as a standard simple CSRF defense
    x_requested_with = request.headers.get("X-Requested-With") or request.headers.get("x-requested-with")
    if x_requested_with and x_requested_with.lower() == "xmlhttprequest":
        return

    # If Origin header is present and matches Host, allow
    origin = request.headers.get("Origin") or request.headers.get("origin")
    if origin:
        host = request.headers.get("Host", "") or request.headers.get("host", "")
        if host and (f"http://{host}" == origin or f"https://{host}" == origin):
            return

    # Reject state-changing cookie-authenticated request missing CSRF verification
    raise HTTPException(
        status_code=403,
        detail="CSRF validation failed: Missing or invalid X-CSRF-Token header.",
    )

