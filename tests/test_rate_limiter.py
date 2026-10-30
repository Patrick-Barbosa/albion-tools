"""Rate limiter síncrono do cliente AODP (stdlib puro)."""

import pytest

from _albion_core.http import RateLimitError, RateLimiter


def test_status_reports_official_limits():
    limiter = RateLimiter()
    status = limiter.status()
    assert status["health"] == "EXCELENTE"
    assert status["window_1_minute"]["remaining"] == limiter.max_per_minute
    assert "180 req/min" in status["official_limits_note"]


def test_acquire_increments_counters():
    limiter = RateLimiter()
    limiter.acquire(wait=False)
    limiter.acquire(wait=False)
    status = limiter.status()
    assert status["window_1_minute"]["used"] == 2
    assert status["window_5_minutes"]["used"] == 2
    assert status["total_requests_made"] == 2


def test_limit_per_minute_raises_without_waiting():
    limiter = RateLimiter(max_per_minute=2, max_per_5_minutes=100)
    limiter.acquire(wait=False)
    limiter.acquire(wait=False)
    with pytest.raises(RateLimitError):
        limiter.acquire(wait=False)
    assert limiter.blocked_attempts == 1


def test_limit_per_five_minutes_raises():
    limiter = RateLimiter(max_per_minute=100, max_per_5_minutes=1)
    limiter.acquire(wait=False)
    with pytest.raises(RateLimitError):
        limiter.acquire(wait=False)


def test_health_degrades_when_quota_is_low():
    limiter = RateLimiter(max_per_minute=10, max_per_5_minutes=10)
    for _ in range(9):
        limiter.acquire(wait=False)
    assert limiter.status()["health"] == "CRITICO"
