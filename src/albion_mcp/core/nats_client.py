"""
Cliente NATS Firehose para Streaming e Buffer em Tempo Real do Albion Online.

Conecta-se ao broker público oficial:
nats://public:thenewalbiondata@nats.albion-online-data.com:4222

Permite que agentes consultem cotações 100% ao vivo (< 60s) e detectem
ordens imediatas de compra do Mercado Negro (Caerleon Black Market - Loc 3003)
sem consumir cota de requisições da REST API da AODP.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional
import nats

logger = logging.getLogger("albion_mcp.nats_client")

NATS_BROKER_URL = "nats://public:thenewalbiondata@nats.albion-online-data.com:4222"

LOCATION_ID_TO_CITY = {
    3003: "Black Market",
    3005: "Caerleon",
    1002: "Lymhurst",
    1000: "Lymhurst",
    2004: "Bridgewatch",
    2000: "Bridgewatch",
    3008: "Martlock",
    3000: "Martlock",
    4002: "Fort Sterling",
    4000: "Fort Sterling",
    7: "Thetford",
    5003: "Brecilien",
}

CITY_TO_LOCATION_ID = {v.lower(): k for k, v in LOCATION_ID_TO_CITY.items()}


class NATSMarketSubscriber:
    def __init__(self, broker_url: str = NATS_BROKER_URL):
        self.broker_url = broker_url
        self.nc: Optional[nats.NATS] = None
        self._is_running = False
        self._task: Optional[asyncio.Task] = None

        # Buffers em memória:
        # (item_id, quality, city) -> order dict
        self.live_orders: Dict[tuple, Dict[str, Any]] = {}
        # Black market buy requests
        self.bm_requests: Dict[tuple, Dict[str, Any]] = {}

        self.messages_received: int = 0
        self.last_message_time: float = 0.0

    async def start(self):
        """Inicia a conexão e assinatura NATS em segundo plano."""
        if self._is_running:
            return

        self._is_running = True
        self._task = asyncio.create_task(self._subscriber_loop())
        logger.info("NATS Market Subscriber iniciado.")

    async def stop(self):
        """Para a assinatura e desconecta do NATS."""
        self._is_running = False
        if self.nc and not self.nc.is_closed:
            try:
                await self.nc.drain()
                await self.nc.close()
            except Exception:
                pass
        if self._task:
            self._task.cancel()
        logger.info("NATS Market Subscriber encerrado.")

    async def _subscriber_loop(self):
        while self._is_running:
            try:
                logger.info(f"Conectando ao NATS em {self.broker_url}...")
                self.nc = await nats.connect(
                    self.broker_url,
                    connect_timeout=10,
                    reconnect_time_wait=2,
                    max_reconnect_attempts=-1,
                )
                logger.info("Conectado com sucesso ao NATS Firehose!")

                sub = await self.nc.subscribe("marketorders.*")
                async for msg in sub.messages:
                    if not self._is_running:
                        break
                    self._process_message(msg.data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Erro na conexão NATS: {e}. Reconectando em 5 segundos...")
                await asyncio.sleep(5.0)

    def _process_message(self, raw_bytes: bytes):
        try:
            self.messages_received += 1
            self.last_message_time = time.time()
            data = json.loads(raw_bytes.decode("utf-8"))

            item_id = data.get("ItemTypeId")
            loc_id = data.get("LocationId")
            quality = data.get("QualityLevel", 1)
            price = data.get("UnitPriceSilver", 0)
            amount = data.get("Amount", 0)
            auction_type = data.get("AuctionType", "offer")  # 'offer' = sell order, 'request' = buy order

            if not item_id or not loc_id or price <= 0:
                return

            city = LOCATION_ID_TO_CITY.get(loc_id, f"Loc_{loc_id}")
            key = (item_id, quality, city)

            order_payload = {
                "item_id": item_id,
                "quality": quality,
                "city": city,
                "location_id": loc_id,
                "price": price,
                "amount": amount,
                "auction_type": auction_type,
                "received_at": self.last_message_time,
                "received_at_iso": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(self.last_message_time))
            }

            self.live_orders[key] = order_payload

            # Filtro especial do Black Market (Ordens de compra do sistema)
            if loc_id == 3003 and auction_type == "request":
                self.bm_requests[(item_id, quality)] = order_payload

        except Exception:
            pass

    def get_live_orders(
        self,
        item_ids: Optional[List[str]] = None,
        cities: Optional[List[str]] = None,
        qualities: Optional[List[int]] = None,
        max_age_seconds: float = 600.0
    ) -> List[Dict[str, Any]]:
        """Retorna ordens recentes filtradas com base no buffer em memória."""
        now = time.time()
        results = []

        target_items = set(item_ids) if item_ids else None
        target_cities = set(c.lower() for c in cities) if cities else None
        target_qualities = set(qualities) if qualities else None

        for (it, q, c), order in list(self.live_orders.items()):
            # Checa validade temporal
            if now - order["received_at"] > max_age_seconds:
                continue
            if target_items and it not in target_items:
                continue
            if target_cities and c.lower() not in target_cities:
                continue
            if target_qualities and q not in target_qualities:
                continue

            order_copy = dict(order)
            order_copy["age_seconds"] = int(now - order["received_at"])
            results.append(order_copy)

        return results

    def get_black_market_opportunities(
        self,
        item_ids: Optional[List[str]] = None,
        max_age_seconds: float = 900.0
    ) -> List[Dict[str, Any]]:
        """Retorna as ordens de compra abertas do Black Market presentes no buffer."""
        now = time.time()
        results = []
        target_items = set(item_ids) if item_ids else None

        for (it, q), order in list(self.bm_requests.items()):
            if now - order["received_at"] > max_age_seconds:
                continue
            if target_items and it not in target_items:
                continue

            order_copy = dict(order)
            order_copy["age_seconds"] = int(now - order["received_at"])
            results.append(order_copy)

        results.sort(key=lambda x: x["price"], reverse=True)
        return results

    def get_status(self) -> Dict[str, Any]:
        """Retorna o status da conexão NATS."""
        now = time.time()
        is_connected = self.nc is not None and self.nc.is_connected
        return {
            "status": "connected" if is_connected else "disconnected",
            "broker_url": self.broker_url,
            "messages_received": self.messages_received,
            "buffered_orders_count": len(self.live_orders),
            "black_market_requests_count": len(self.bm_requests),
            "last_message_age_seconds": round(now - self.last_message_time, 1) if self.last_message_time > 0 else None,
            "description": (
                "O stream NATS transmite ordens em tempo real diretamente da rede da comunidade AODP. "
                "Consultas ao buffer NATS possuem latência de milissegundos e não consomem cotas da REST API."
            )
        }


# Instância global NATS
nats_subscriber = NATSMarketSubscriber()
