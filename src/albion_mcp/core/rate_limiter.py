"""
Rate Limiter e Controle de Quota para a API AODP (Albion Online Data Project).

Limites oficiais da AODP:
- 180 requisições por minuto (60 segundos)
- 300 requisições a cada 5 minutos (300 segundos)

Este módulo implementa uma janela deslizante (sliding window) em memória,
com verificação atômica assíncrona, retry com backoff e relatórios de status
de quota para orientar agentes a não esgotarem os limites da API pública.
"""

import asyncio
import time
import logging
from collections import deque
from typing import Dict, Any

logger = logging.getLogger("albion_mcp.rate_limiter")


class RateLimitExceededException(Exception):
    """Exceção levantada quando a taxa de chamadas excede os limites da AODP."""
    def __init__(self, retry_after: float, message: str):
        super().__init__(message)
        self.retry_after = retry_after
        self.message = message


class AODPRateLimiter:
    def __init__(self, max_per_minute: int = 175, max_per_5_minutes: int = 290):
        # Usamos uma margem de segurança ligeiramente abaixo de 180 e 300 para prevenir bloqueios de IP
        self.max_per_minute = max_per_minute
        self.max_per_5_minutes = max_per_5_minutes
        self._lock = asyncio.Lock()
        self._requests_1m: deque[float] = deque()
        self._requests_5m: deque[float] = deque()
        self._total_requests_made: int = 0
        self._blocked_requests_count: int = 0

    def _cleanup(self, now: float):
        """Remove registros fora das janelas temporais."""
        cutoff_1m = now - 60.0
        while self._requests_1m and self._requests_1m[0] <= cutoff_1m:
            self._requests_1m.popleft()

        cutoff_5m = now - 300.0
        while self._requests_5m and self._requests_5m[0] <= cutoff_5m:
            self._requests_5m.popleft()

    async def acquire(self, wait_if_needed: bool = True, max_wait_seconds: float = 15.0) -> bool:
        """
        Solicita permissão para disparar uma requisição HTTP.
        Se wait_if_needed=True, aguarda caso o limite esteja próximo até max_wait_seconds.
        Caso contrário, levanta RateLimitExceededException.
        """
        async with self._lock:
            now = time.time()
            self._cleanup(now)

            # Verifica limites
            wait_time = 0.0
            if len(self._requests_1m) >= self.max_per_minute:
                wait_time = max(wait_time, 60.0 - (now - self._requests_1m[0]) + 0.1)

            if len(self._requests_5m) >= self.max_per_5_minutes:
                wait_time = max(wait_time, 300.0 - (now - self._requests_5m[0]) + 0.1)

            if wait_time > 0:
                self._blocked_requests_count += 1
                if not wait_if_needed or wait_time > max_wait_seconds:
                    logger.warning(
                        f"Rate limit atingido! Requisições 1m: {len(self._requests_1m)}/{self.max_per_minute}, "
                        f"5m: {len(self._requests_5m)}/{self.max_per_5_minutes}. Aguardar {wait_time:.1f}s."
                    )
                    raise RateLimitExceededException(
                        retry_after=round(wait_time, 2),
                        message=(
                            f"Limite de requisições da API pública do Albion Online atingido. "
                            f"Aguarde {wait_time:.1f}s antes de novas consultas. "
                            f"Dica: Agrupe vários itens em uma única chamada (batching) ou consulte o buffer NATS."
                        )
                    )

                logger.info(f"Rate limiter em pausa preventiva por {wait_time:.2f}s...")
                await asyncio.sleep(wait_time)
                now = time.time()
                self._cleanup(now)

            # Registra requisição autorizada
            self._requests_1m.append(now)
            self._requests_5m.append(now)
            self._total_requests_made += 1
            return True

    def get_status(self) -> Dict[str, Any]:
        """Retorna as estatísticas atuais de consumo da API."""
        now = time.time()
        self._cleanup(now)

        used_1m = len(self._requests_1m)
        used_5m = len(self._requests_5m)

        remaining_1m = max(0, self.max_per_minute - used_1m)
        remaining_5m = max(0, self.max_per_5_minutes - used_5m)

        health = "EXCELENTE"
        if remaining_1m < 30 or remaining_5m < 50:
            health = "CRITICO"
        elif remaining_1m < 80 or remaining_5m < 120:
            health = "ATENCAO"

        return {
            "health": health,
            "window_1_minute": {
                "used": used_1m,
                "limit": self.max_per_minute,
                "remaining": remaining_1m,
                "usage_pct": round((used_1m / self.max_per_minute) * 100, 1)
            },
            "window_5_minutes": {
                "used": used_5m,
                "limit": self.max_per_5_minutes,
                "remaining": remaining_5m,
                "usage_pct": round((used_5m / self.max_per_5_minutes) * 100, 1)
            },
            "total_requests_made": self._total_requests_made,
            "blocked_attempts": self._blocked_requests_count,
            "official_limits_note": (
                "Limites oficiais da AODP: 180 req/min, 300 req/5min. "
                "O MCP utiliza margem de segurança (175/min e 290/5min) e batching automático."
            )
        }


# Instância global do Rate Limiter
rate_limiter = AODPRateLimiter()
