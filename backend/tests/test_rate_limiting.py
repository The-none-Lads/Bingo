import asyncio
import pytest
from auth.rate_limit import RateLimiter


@pytest.mark.asyncio
class TestRateLimiting:
    async def test_ip_rate_limiting(self):
        limiter = RateLimiter(ip_limit=3, ip_window_seconds=2)
        ip = "192.168.1.100"

        # First 3 attempts are allowed
        for _ in range(3):
            allowed, _ = await limiter.check_ip_limit(ip)
            assert allowed is True
            await limiter.record_ip_attempt(ip)

        # 4th attempt is blocked
        allowed, retry_after = await limiter.check_ip_limit(ip)
        assert allowed is False
        assert retry_after is not None and retry_after > 0

        # Different IP is not blocked
        other_ip_allowed, _ = await limiter.check_ip_limit("192.168.1.101")
        assert other_ip_allowed is True

    async def test_account_progressive_throttling_and_cooldown(self):
        limiter = RateLimiter(
            account_cooldown_attempts=5,
            account_cooldown_seconds=3,
        )
        account = "target_user"

        # 1st and 2nd attempts: no backoff
        for _ in range(2):
            allowed, _ = await limiter.check_account_status(account)
            assert allowed is True
            await limiter.record_account_failure(account)

        # 3rd failure triggers 1s progressive backoff
        await limiter.record_account_failure(account)
        allowed, retry_after = await limiter.check_account_status(account)
        assert allowed is False
        assert retry_after is not None and retry_after <= 2

        # After waiting 1.1s, next attempt is allowed
        await asyncio.sleep(1.1)
        allowed, _ = await limiter.check_account_status(account)
        assert allowed is True

        # Reaching 5 failures triggers cooldown
        await limiter.record_account_failure(account)  # 4th
        await limiter.record_account_failure(account)  # 5th

        allowed, cooldown = await limiter.check_account_status(account)
        assert allowed is False
        assert cooldown is not None and cooldown > 0

    async def test_account_success_resets_counter(self):
        limiter = RateLimiter(account_cooldown_attempts=5, account_cooldown_seconds=300)
        account = "recovering_user"

        for _ in range(3):
            await limiter.record_account_failure(account)

        # Successful login
        await limiter.record_account_success(account)

        # Status is immediately clear
        allowed, retry_after = await limiter.check_account_status(account)
        assert allowed is True
        assert retry_after is None
