"""
Testes unitários para o Rate Limiter e controle de quota da API AODP.
"""

import asyncio
import pytest
from src.albion_mcp.core.rate_limiter import AODPRateLimiter, RateLimitExceededException


def test_rate_limiter_basic():
    async def _run():
        limiter = AODPRateLimiter(max_per_minute=5, max_per_5_minutes=10)
        for _ in range(5):
            allowed = await limiter.acquire(wait_if_needed=False)
            assert allowed is True

        # Sexta chamada no mesmo minuto deve estourar
        with pytest.raises(RateLimitExceededException):
            await limiter.acquire(wait_if_needed=False)

        status = limiter.get_status()
        assert status["window_1_minute"]["used"] == 5
        assert status["window_1_minute"]["remaining"] == 0
        assert status["health"] == "CRITICO"

    asyncio.run(_run())
