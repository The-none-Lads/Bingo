import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware injecting standard browser security headers.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Non-breaking Content-Security-Policy for React + Vite SPA with WebSocket
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' ws: wss: http: https:; "
            "font-src 'self' data:; "
            "frame-ancestors 'self';"
        )
        response.headers["Content-Security-Policy"] = csp

        # HSTS only when explicitly enabled or running in production with HTTPS
        if os.getenv("ENFORCE_HSTS", "false").lower() in ("true", "1", "yes"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
