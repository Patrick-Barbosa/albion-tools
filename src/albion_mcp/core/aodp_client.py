"""
Cliente Assíncrono para a REST API do Albion Online Data Project (AODP).

Features críticas:
1. Batching Inteligente: Concatena dezenas de item_ids por requisição HTTP,
   evitando chamadas unitárias e respeitando o limite de 4096 caracteres na URL.
2. Rate Limiter Integrado: Janela de proteção ativa (175 req/min e 290 req/5min).
3. Cache em Memória com TTL: Previne que loops de raciocínio de agentes agênticos
   re-consultem os mesmos dados consecutivamente.
4. Backoff em HTTP 429: Recuperação suave com tempo de espera respeitoso.
"""

import asyncio
import time
import logging
from typing import List, Dict, Any, Optional
import httpx

from .rate_limiter import rate_limiter, RateLimitExceededException

logger = logging.getLogger("albion_mcp.aodp_client")

REGION_URLS = {
    "americas": "https://west.albion-online-data.com",
    "west": "https://west.albion-online-data.com",
    "asia": "https://east.albion-online-data.com",
    "east": "https://east.albion-online-data.com",
    "europe": "https://europe.albion-online-data.com",
}

DEFAULT_LOCATIONS = ["Bridgewatch", "Lymhurst", "Fort Sterling", "Martlock", "Thetford", "Caerleon", "Black Market", "Brecilien"]


class AODPClient:
    def __init__(self, default_region: str = "americas"):
        self.default_region = default_region.lower()
        self._price_cache: Dict[str, Dict[str, Any]] = {}
        self._history_cache: Dict[str, Dict[str, Any]] = {}
        self._gold_cache: Dict[str, Dict[str, Any]] = {}

        # TTLs em segundos
        self.price_cache_ttl = 120.0       # 2 minutos
        self.history_cache_ttl = 1800.0     # 30 minutos
        self.gold_cache_ttl = 300.0         # 5 minutos

    def get_base_url(self, region: Optional[str] = None) -> str:
        r = (region or self.default_region).lower()
        return REGION_URLS.get(r, REGION_URLS["americas"])

    def _chunk_items(self, item_ids: List[str], max_chunk_size: int = 50) -> List[List[str]]:
        """Divide listas grandes de itens em blocos para não ultrapassar 4096 caracteres na URL."""
        chunks = []
        current_chunk = []
        current_len = 0

        for it in item_ids:
            it_clean = it.strip()
            if not it_clean:
                continue
            # Verifica comprimento se adicionado
            if len(current_chunk) >= max_chunk_size or (current_len + len(it_clean) + 1 > 3000):
                chunks.append(current_chunk)
                current_chunk = [it_clean]
                current_len = len(it_clean)
            else:
                current_chunk.append(it_clean)
                current_len += len(it_clean) + 1

        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    async def get_current_prices(
        self,
        item_ids: List[str],
        locations: Optional[List[str]] = None,
        qualities: Optional[List[int]] = None,
        region: Optional[str] = None,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Consulta os preços atuais de compra e venda (min/max order prices) para itens no AODP.
        Aplica batching automático e cache para máxima eficiência de quota.
        """
        if not item_ids:
            return []

        base_url = self.get_base_url(region)
        locs = locations or DEFAULT_LOCATIONS
        loc_str = ",".join(locs)
        qual_str = ",".join(str(q) for q in (qualities or [1, 2, 3, 4, 5]))

        results = []
        missing_items = []
        now = time.time()

        # Checa cache individual de itens
        for it in item_ids:
            cache_key = f"{base_url}:{it}:{loc_str}:{qual_str}"
            if use_cache and cache_key in self._price_cache:
                cached = self._price_cache[cache_key]
                if now - cached["ts"] < self.price_cache_ttl:
                    results.extend(cached["data"])
                    continue
            missing_items.append(it)

        if not missing_items:
            return results

        # Processa itens pendentes em lotes (batching)
        chunks = self._chunk_items(missing_items)
        async with httpx.AsyncClient(timeout=15.0) as client:
            for chunk in chunks:
                items_param = ",".join(chunk)
                url = f"{base_url}/api/v2/stats/prices/{items_param}.json"
                params = {"locations": loc_str, "qualities": qual_str}

                # Respeita o Rate Limiter com margem de segurança
                await rate_limiter.acquire(wait_if_needed=True)

                retries = 3
                for attempt in range(retries):
                    try:
                        resp = await client.get(url, params=params, headers={"User-Agent": "albion-mcp/2.0"})
                        if resp.status_code == 200:
                            data = resp.json()
                            results.extend(data)

                            # Alimenta cache por item
                            chunk_data_by_item: Dict[str, List[Dict[str, Any]]] = {i: [] for i in chunk}
                            for row in data:
                                i_id = row.get("item_id")
                                if i_id in chunk_data_by_item:
                                    chunk_data_by_item[i_id].append(row)

                            for i_id, i_data in chunk_data_by_item.items():
                                c_key = f"{base_url}:{i_id}:{loc_str}:{qual_str}"
                                self._price_cache[c_key] = {"ts": now, "data": i_data}
                            break
                        elif resp.status_code == 429:
                            wait_s = 2.0 * (attempt + 1)
                            logger.warning(f"HTTP 429 Too Many Requests da AODP. Aguardando {wait_s}s...")
                            await asyncio.sleep(wait_s)
                        else:
                            logger.warning(f"AODP retornou status {resp.status_code} para {url}")
                            break
                    except Exception as e:
                        if attempt == retries - 1:
                            logger.error(f"Erro ao consultar AODP preços: {e}")
                        await asyncio.sleep(1.0)

        return results

    async def get_price_history(
        self,
        item_ids: List[str],
        locations: Optional[List[str]] = None,
        qualities: Optional[List[int]] = None,
        time_scale: int = 24,
        region: Optional[str] = None,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Consulta histórico de transações e volume diário no AODP (Sell orders).
        time_scale: 1 (horas) ou 24 (dias).
        """
        if not item_ids:
            return []

        base_url = self.get_base_url(region)
        locs = locations or DEFAULT_LOCATIONS
        loc_str = ",".join(locs)
        qual_str = ",".join(str(q) for q in (qualities or [1]))

        results = []
        missing_items = []
        now = time.time()

        for it in item_ids:
            cache_key = f"{base_url}:{it}:{loc_str}:{qual_str}:{time_scale}"
            if use_cache and cache_key in self._history_cache:
                cached = self._history_cache[cache_key]
                if now - cached["ts"] < self.history_cache_ttl:
                    results.extend(cached["data"])
                    continue
            missing_items.append(it)

        if not missing_items:
            return results

        chunks = self._chunk_items(missing_items, max_chunk_size=20)
        async with httpx.AsyncClient(timeout=20.0) as client:
            for chunk in chunks:
                items_param = ",".join(chunk)
                url = f"{base_url}/api/v2/stats/history/{items_param}.json"
                params = {
                    "locations": loc_str,
                    "qualities": qual_str,
                    "time-scale": time_scale
                }

                await rate_limiter.acquire(wait_if_needed=True)

                try:
                    resp = await client.get(url, params=params, headers={"User-Agent": "albion-mcp/2.0"})
                    if resp.status_code == 200:
                        data = resp.json()
                        results.extend(data)

                        # Armazena no cache
                        for row in data:
                            i_id = row.get("item_id")
                            if i_id:
                                c_key = f"{base_url}:{i_id}:{loc_str}:{qual_str}:{time_scale}"
                                self._history_cache[c_key] = {"ts": now, "data": [row]}
                    elif resp.status_code == 429:
                        logger.warning("HTTP 429 ao buscar histórico.")
                except Exception as e:
                    logger.error(f"Erro ao buscar histórico AODP: {e}")

        return results

    async def get_gold_prices(self, count: int = 50, region: Optional[str] = None) -> List[Dict[str, Any]]:
        """Consulta as cotações recentes de Ouro (Gold)."""
        base_url = self.get_base_url(region)
        cache_key = f"{base_url}:gold:{count}"
        now = time.time()

        if cache_key in self._gold_cache:
            cached = self._gold_cache[cache_key]
            if now - cached["ts"] < self.gold_cache_ttl:
                return cached["data"]

        await rate_limiter.acquire(wait_if_needed=True)

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                url = f"{base_url}/api/v2/stats/gold.json"
                resp = await client.get(url, params={"count": count}, headers={"User-Agent": "albion-mcp/2.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    self._gold_cache[cache_key] = {"ts": now, "data": data}
                    return data
            except Exception as e:
                logger.error(f"Erro ao obter preço do ouro: {e}")

        return []


# Instância global do cliente AODP
aodp_client = AODPClient()
