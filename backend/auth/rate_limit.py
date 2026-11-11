import asyncio
import time
from typing import Dict, Optional, Tuple


class RateLimiter:
    """
    In-memory rate limiter with per-IP sliding window limits and
    per-account progressive backoff / temporary cooldown.
    """

    def __init__(
        self,
        ip_limit: int = 10,
        ip_window_seconds: int = 60,
        account_cooldown_attempts: int = 5,
        account_cooldown_seconds: int = 300,
    ):
        self.ip_limit = ip_limit
        self.ip_window_seconds = ip_window_seconds
        self.account_cooldown_attempts = account_cooldown_attempts
        self.account_cooldown_seconds = account_cooldown_seconds

        # IP tracking: {ip: [timestamp, ...]}
        self._ip_attempts: Dict[str, list[float]] = {}
        # Account tracking: {identifier: {"count": int, "locked_until": float, "last_attempt": float}}
        self._account_attempts: Dict[str, Dict[str, float]] = {}
        self._lock = asyncio.Lock()

    def _cleanup_ip(self, ip: str, now: float) -> list[float]:
        cutoff = now - self.ip_window_seconds
        attempts = [t for t in self._ip_attempts.get(ip, []) if t > cutoff]
        self._ip_attempts[ip] = attempts
        return attempts

    async def check_ip_limit(self, ip: str) -> Tuple[bool, Optional[int]]:
        """
        Check whether an IP has exceeded its allowed attempt limit.
        Returns (is_allowed, retry_after_seconds).
        """
        if not ip:
            return True, None

        now = time.time()
        async with self._lock:
            attempts = self._cleanup_ip(ip, now)
            if len(attempts) >= self.ip_limit:
                oldest = attempts[0]
                retry_after = max(1, int(oldest + self.ip_window_seconds - now))
                return False, retry_after
            return True, None

    async def record_ip_attempt(self, ip: str) -> None:
        """Record an attempt from an IP."""
        if not ip:
            return
        now = time.time()
        async with self._lock:
            attempts = self._cleanup_ip(ip, now)
            attempts.append(now)
            self._ip_attempts[ip] = attempts

    async def check_account_status(self, identifier: str) -> Tuple[bool, Optional[int]]:
        """
        Check whether an account is temporarily in progressive backoff / cooldown.
        Returns (is_allowed, retry_after_seconds).
        """
        if not identifier:
            return True, None

        key = identifier.lower().strip()
        now = time.time()
        async with self._lock:
            data = self._account_attempts.get(key)
            if not data:
                return True, None

            locked_until = data.get("locked_until", 0)
            if locked_until > now:
                return False, max(1, int(locked_until - now))

            # Progressive backoff for 3 or 4 consecutive failures
            count = data.get("count", 0)
            last_attempt = data.get("last_attempt", 0)
            if count >= 3:
                # Delay of 2^(count - 3) seconds (e.g. 1s, 2s)
                delay = 2 ** (count - 3)
                if now < last_attempt + delay:
                    retry_after = max(1, int(last_attempt + delay - now))
                    return False, retry_after

            return True, None

    async def record_account_failure(self, identifier: str) -> None:
        """Record a failed login attempt for an account identifier."""
        if not identifier:
            return

        key = identifier.lower().strip()
        now = time.time()
        async with self._lock:
            data = self._account_attempts.get(key)
            if not data:
                self._account_attempts[key] = {
                    "count": 1,
                    "locked_until": 0,
                    "last_attempt": now,
                }
                return

            # If previous cooldown expired, decay count
            if data["locked_until"] > 0 and data["locked_until"] <= now:
                data["count"] = 0
                data["locked_until"] = 0

            data["count"] += 1
            data["last_attempt"] = now

            if data["count"] >= self.account_cooldown_attempts:
                data["locked_until"] = now + self.account_cooldown_seconds

    async def record_account_success(self, identifier: str) -> None:
        """Reset failed attempt counters upon successful authentication."""
        if not identifier:
            return
        key = identifier.lower().strip()
        async with self._lock:
            self._account_attempts.pop(key, None)

    async def reset(self) -> None:
        """Reset all rate limiter state (mainly for tests)."""
        async with self._lock:
            self._ip_attempts.clear()
            self._account_attempts.clear()


# Global rate limiter instance for auth endpoints
auth_rate_limiter = RateLimiter(
    ip_limit=10,
    ip_window_seconds=60,
    account_cooldown_attempts=5,
    account_cooldown_seconds=300,
)
