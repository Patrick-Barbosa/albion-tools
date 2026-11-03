"""
Cliente HTTP síncrono para a API pública do Albion Online Data Project (AODP).

Sem dependências externas: usa apenas `urllib` da biblioteca padrão.

Recursos:
1. Batching automático (até 50 itens por GET, respeitando 4096 caracteres de URL).
2. Rate limiter em janela deslizante (175 req/min e 290 req/5min).
3. Cache em memória com TTL (120s cotações, 30min histórico/ouro).
4. Backoff automático em HTTP 429.
"""

from __future__ import annotations

import gzip
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("albion_core.http")

USER_AGENT = "albion-skills/3.0 (+https://github.com/Patrick-Barbosa/albion-tools)"

REGION_URLS = {
    "americas": "https://west.albion-online-data.com",
    "west": "https://west.albion-online-data.com",
    "asia": "https://east.albion-online-data.com",
    "east": "https://east.albion-online-data.com",
    "europe": "https://europe.albion-online-data.com",
}

ROYAL_CITIES = ["Bridgewatch", "Lymhurst", "Fort Sterling", "Martlock", "Thetford"]
ALL_LOCATIONS = ROYAL_CITIES + ["Caerleon", "Black Market", "Brecilien"]

MAX_URL_CHARS = 4096
MAX_ITEMS_PER_CHUNK = 50


class RateLimitError(RuntimeError):
    """Levantada quando a cota local da AODP é insuficiente para a chamada."""

    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(
            f"Cota local da AODP esgotada. Aguarde ~{retry_after:.0f}s ou agrupe mais itens por chamada."
        )


class RateLimiter:
    """Janela deslizante síncrona com margem de segurança sobre os limites oficiais."""

    def __init__(self, max_per_minute: int = 175, max_per_5_minutes: int = 290):
        self.max_per_minute = max_per_minute
        self.max_per_5_minutes = max_per_5_minutes
        self._requests_1m: deque[float] = deque()
        self._requests_5m: deque[float] = deque()
        self.total_requests = 0
        self.blocked_attempts = 0

    def _cleanup(self, now: float) -> None:
        while self._requests_1m and self._requests_1m[0] <= now - 60.0:
            self._requests_1m.popleft()
        while self._requests_5m and self._requests_5m[0] <= now - 300.0:
            self._requests_5m.popleft()

    def acquire(self, wait: bool = True, max_wait: float = 30.0) -> None:
        now = time.time()
        self._cleanup(now)

        wait_time = 0.0
        if len(self._requests_1m) >= self.max_per_minute:
            wait_time = max(wait_time, 60.0 - (now - self._requests_1m[0]) + 0.1)
        if len(self._requests_5m) >= self.max_per_5_minutes:
            wait_time = max(wait_time, 300.0 - (now - self._requests_5m[0]) + 0.1)

        if wait_time > 0:
            self.blocked_attempts += 1
            if not wait or wait_time > max_wait:
                raise RateLimitError(wait_time)
            logger.info("Rate limiter: pausa preventiva de %.1fs", wait_time)
            time.sleep(wait_time)
            now = time.time()
            self._cleanup(now)

        self._requests_1m.append(now)
        self._requests_5m.append(now)
        self.total_requests += 1

    def status(self) -> Dict[str, Any]:
        now = time.time()
        self._cleanup(now)
        used_1m, used_5m = len(self._requests_1m), len(self._requests_5m)
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
                "usage_pct": round(used_1m / self.max_per_minute * 100, 1),
            },
            "window_5_minutes": {
                "used": used_5m,
                "limit": self.max_per_5_minutes,
                "remaining": remaining_5m,
                "usage_pct": round(used_5m / self.max_per_5_minutes * 100, 1),
            },
            "total_requests_made": self.total_requests,
            "blocked_attempts": self.blocked_attempts,
            "official_limits_note": "Limites oficiais da AODP: 180 req/min e 300 req/5min.",
        }


rate_limiter = RateLimiter()


class AODPClient:
    def __init__(self, default_region: str = "americas"):
        self.default_region = default_region.lower()
        self.price_cache_ttl = 120.0
        self.history_cache_ttl = 1800.0
        self._cache: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ utils
    def base_url(self, region: Optional[str] = None) -> str:
        key = (region or self.default_region).lower()
        if key not in REGION_URLS:
            raise ValueError(
                f"Região '{region}' inválida. Use: {', '.join(sorted(set(REGION_URLS)))}."
            )
        return REGION_URLS[key]

    @staticmethod
    def _chunk(item_ids: List[str], max_items: int = MAX_ITEMS_PER_CHUNK) -> List[List[str]]:
        chunks: List[List[str]] = []
        current: List[str] = []
        for item in item_ids:
            # +1 pelo separador que será adicionado
            if current and (
                len(current) >= max_items
                or len(",".join(current + [item])) > MAX_URL_CHARS - 200
            ):
                chunks.append(current)
                current = [item]
            else:
                current.append(item)
        if current:
            chunks.append(current)
        return chunks

    def _cached(self, key: str, ttl: float) -> Optional[Any]:
        hit = self._cache.get(key)
        if hit and time.time() - hit["ts"] < ttl:
            return hit["data"]
        return None

    def _store(self, key: str, data: Any) -> None:
        self._cache[key] = {"ts": time.time(), "data": data}

    def _get_json(self, url: str, params: Dict[str, Any], retries: int = 4) -> Any:
        query = urllib.parse.urlencode(params)
        full_url = f"{url}?{query}" if query else url

        for attempt in range(retries):
            rate_limiter.acquire(wait=True)
            request = urllib.request.Request(
                full_url,
                headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"},
            )
            try:
                with urllib.request.urlopen(request, timeout=25) as response:
                    raw = response.read()
                    encoding = (response.headers.get("Content-Encoding") or "").lower()
                    if encoding == "gzip":
                        raw = gzip.decompress(raw)
                    elif encoding == "deflate":
                        raw = zlib.decompress(raw)
                    return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                # A AODP exige compressão; 429 também aparece em picos de tráfego.
                if exc.code in (429, 503):
                    backoff = 3.0 * (attempt + 1)
                    logger.warning("AODP respondeu %s; aguardando %.0fs", exc.code, backoff)
                    time.sleep(backoff)
                    continue
                if exc.code in (502, 504):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                logger.warning("AODP retornou HTTP %s para %s", exc.code, full_url)
                return []
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                if attempt == retries - 1:
                    logger.warning("Falha ao consultar AODP (%s): %s", full_url, exc)
                    return []
                time.sleep(1.0 * (attempt + 1))
        return []

    # --------------------------------------------------------------- endpoints
    def get_prices(
        self,
        item_ids: List[str],
        locations: Optional[List[str]] = None,
        qualities: Optional[List[int]] = None,
        region: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """Cotações atuais: menor sell order e maior buy order por item/cidade/qualidade."""
        if not item_ids:
            return []

        base = self.base_url(region)
        locs = locations or ALL_LOCATIONS
        quals = qualities or [1, 2, 3, 4, 5]
        loc_str, qual_str = ",".join(locs), ",".join(str(q) for q in quals)

        results: List[Dict[str, Any]] = []
        pending: List[str] = []

        for item in item_ids:
            key = f"prices|{base}|{item}|{loc_str}|{qual_str}"
            cached = self._cached(key, self.price_cache_ttl) if use_cache else None
            if cached is not None:
                results.extend(cached)
            else:
                pending.append(item)

        for chunk in self._chunk(pending):
            url = f"{base}/api/v2/stats/prices/{','.join(chunk)}.json"
            data = self._get_json(url, {"locations": loc_str, "qualities": qual_str})
            if not isinstance(data, list):
                continue

            by_item: Dict[str, List[Dict[str, Any]]] = {i: [] for i in chunk}
            for row in data:
                by_item.setdefault(row.get("item_id"), []).append(row)

            for item, rows in by_item.items():
                key = f"prices|{base}|{item}|{loc_str}|{qual_str}"
                self._store(key, rows)
                results.extend(rows)

        return results

    def get_history(
        self,
        item_ids: List[str],
        locations: Optional[List[str]] = None,
        qualities: Optional[List[int]] = None,
        time_scale: int = 24,
        days: int = 7,
        region: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Histórico de transações. `time_scale`: 1 (hora) ou 24 (dia).
        Retorna os mesmos objetos da AODP, com o array `data` intacto.
        """
        if not item_ids:
            return []

        base = self.base_url(region)
        locs = locations or ALL_LOCATIONS
        quals = qualities or [1]
        loc_str, qual_str = ",".join(locs), ",".join(str(q) for q in quals)

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=max(1, days))
        params = {
            "date": start.strftime("%m-%d-%Y"),
            "end_date": end.strftime("%m-%d-%Y"),
            "locations": loc_str,
            "qualities": qual_str,
            "time-scale": time_scale,
        }

        results: List[Dict[str, Any]] = []
        pending: List[str] = []

        for item in item_ids:
            key = f"history|{base}|{item}|{loc_str}|{qual_str}|{time_scale}|{params['date']}"
            cached = self._cached(key, self.history_cache_ttl) if use_cache else None
            if cached is not None:
                results.extend(cached)
            else:
                pending.append(item)

        for chunk in self._chunk(pending, max_items=20):
            url = f"{base}/api/v2/stats/history/{','.join(chunk)}.json"
            data = self._get_json(url, params)
            if not isinstance(data, list):
                continue
            by_item: Dict[str, List[Dict[str, Any]]] = {i: [] for i in chunk}
            for row in data:
                by_item.setdefault(row.get("item_id"), []).append(row)
            for item, rows in by_item.items():
                key = f"history|{base}|{item}|{loc_str}|{qual_str}|{time_scale}|{params['date']}"
                self._store(key, rows)
                results.extend(rows)

        return results

    def get_gold(self, count: int = 50, region: Optional[str] = None) -> List[Dict[str, Any]]:
        """Histórico recente da cotação do ouro (prata por ouro)."""
        base = self.base_url(region)
        key = f"gold|{base}|{count}"
        cached = self._cached(key, self.history_cache_ttl)
        if cached is not None:
            return cached

        data = self._get_json(f"{base}/api/v2/stats/gold", {"count": count})
        rows = data if isinstance(data, list) else []
        self._store(key, rows)
        return rows

    def quota(self) -> Dict[str, Any]:
        return rate_limiter.status()

    def clear_cache(self) -> None:
        self._cache.clear()


# Instância global — todo o core compartilha o mesmo cache/rate limiter.
aodp = AODPClient()


# ------------------------------------------------------------------ helpers
def average_price(rows: List[Dict[str, Any]]) -> Optional[int]:
    """Média ponderada por volume a partir das linhas de histórico da AODP."""
    total_qty = 0
    total_silver = 0.0
    for row in rows:
        qty = row.get("item_count") or 0
        price = row.get("avg_price") or 0
        if qty > 0 and price > 0:
            total_qty += qty
            total_silver += qty * price
    if total_qty == 0:
        return None
    return int(round(total_silver / total_qty))


def daily_volume(rows: List[Dict[str, Any]]) -> float:
    """Vendas médias por dia (considerando apenas dias com transações)."""
    days = {
        (row.get("timestamp_date") or row.get("timestamp"))
        for row in rows
        if (row.get("item_count") or 0) > 0
    }
    total = sum(row.get("item_count") or 0 for row in rows)
    if not days:
        return 0.0
    return round(total / len(days), 2)
