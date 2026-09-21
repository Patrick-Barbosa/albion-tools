"""
Ferramentas MCP para cotações de mercado ao vivo (REST Batch + NATS Stream) e Quota.
"""

from typing import List, Dict, Any, Optional
from ..core.aodp_client import aodp_client
from ..core.nats_client import nats_subscriber
from ..core.rate_limiter import rate_limiter
from ..core.metadata import metadata_manager, QUALITY_NAMES


async def albion_get_current_prices(
    item_ids: List[str],
    locations: Optional[List[str]] = None,
    qualities: Optional[List[int]] = None,
    region: Optional[str] = "americas"
) -> Dict[str, Any]:
    """
    Consulta cotações atuais de compra e venda (min sell order, max buy order) na API pública da AODP.

    IMPORTANTE - RESSALVAS DE LIMITES BAIXOS DA API:
    - Limite oficial: 180 req/min e 300 req/5min.
    - O MCP aplica BATCHING automático agrupando até 50 itens em uma única chamada HTTP.
    - SEMPRE passe múltiplos itens em `item_ids` de uma vez em vez de chamar esta ferramenta em loop.
    - Se precisar de monitoramento contínuo em tempo real, prefira a ferramenta `albion_nats_get_live_orders`.

    Parâmetros:
    - item_ids: Lista de identificadores de itens (ex: ['T4_BAG', 'T5_BAG', 'T4_MAIN_SWORD']).
    - locations: Lista opcional de cidades (ex: ['Lymhurst', 'Bridgewatch', 'Caerleon', 'Black Market']). Padrão: Todas as cidades reais.
    - qualities: Lista de qualidades (1 a 5). Padrão: 1 a 5.
    - region: Região do servidor ('americas', 'asia', 'europe'). Padrão: 'americas'.
    """
    if not item_ids:
        return {"error": "item_ids não pode estar vazio.", "items": []}

    raw_prices = await aodp_client.get_current_prices(
        item_ids=item_ids,
        locations=locations,
        qualities=qualities,
        region=region
    )

    # Enriquecer com nomes em PT-BR
    enriched = []
    for r in raw_prices:
        i_id = r.get("item_id")
        q_val = r.get("quality", 1)
        enriched.append({
            "item_id": i_id,
            "item_name_pt": metadata_manager.get_item_name(i_id),
            "city": r.get("city"),
            "quality": q_val,
            "quality_name": QUALITY_NAMES.get(q_val, f"Q{q_val}"),
            "sell_price_min": r.get("sell_price_min", 0),
            "sell_price_min_date": r.get("sell_price_min_date"),
            "buy_price_max": r.get("buy_price_max", 0),
            "buy_price_max_date": r.get("buy_price_max_date"),
        })

    quota = rate_limiter.get_status()

    return {
        "region": region,
        "total_quotes": len(enriched),
        "quota_health": quota["health"],
        "remaining_calls_1m": quota["window_1_minute"]["remaining"],
        "quotes": enriched
    }


def albion_nats_get_live_orders(
    item_ids: Optional[List[str]] = None,
    cities: Optional[List[str]] = None,
    qualities: Optional[List[int]] = None,
    max_age_seconds: int = 600,
    only_black_market_requests: bool = False
) -> Dict[str, Any]:
    """
    Consulta o buffer de eventos em tempo real transmitidos via NATS Firehose (< 60s).

    VANTAGENS AGÊNTICAS:
    - CONSUMO ZERO de cota da REST API! Não é afetado pelos limites de 180 req/min.
    - Latência de leitura instantânea em memória RAM (< 1ms).
    - Permite capturar ordens de compra imediatas do Mercado Negro (Location 3003).

    Parâmetros:
    - item_ids: Filtro opcional por IDs de itens específicos.
    - cities: Filtro opcional por cidades (ex: ['Black Market', 'Lymhurst']).
    - qualities: Filtro opcional por qualidades (1 a 5).
    - max_age_seconds: Idade máxima do pacote em segundos (padrão: 600 segundos / 10 minutos).
    - only_black_market_requests: Se True, filtra apenas ordens de compra ativas do Black Market.
    """
    if only_black_market_requests:
        orders = nats_subscriber.get_black_market_opportunities(
            item_ids=item_ids,
            max_age_seconds=float(max_age_seconds)
        )
    else:
        orders = nats_subscriber.get_live_orders(
            item_ids=item_ids,
            cities=cities,
            qualities=qualities,
            max_age_seconds=float(max_age_seconds)
        )

    # Enriquece com nomes em PT-BR
    for o in orders:
        i_id = o.get("item_id")
        q = o.get("quality", 1)
        o["item_name_pt"] = metadata_manager.get_item_name(i_id)
        o["quality_name"] = QUALITY_NAMES.get(q, f"Q{q}")

    nats_status = nats_subscriber.get_status()

    return {
        "stream_status": nats_status["status"],
        "total_live_orders_returned": len(orders),
        "total_buffered_in_memory": nats_status["buffered_orders_count"],
        "orders": orders
    }


async def albion_get_gold_prices(count: int = 24, region: str = "americas") -> Dict[str, Any]:
    """
    Consulta o histórico de preço do Ouro (Gold) em prata no Albion Online.
    
    Parâmetros:
    - count: Número de pontos recentes de preço a retornar (padrão: 24).
    - region: Região do servidor ('americas', 'asia', 'europe').
    """
    gold_data = await aodp_client.get_gold_prices(count=count, region=region)
    return {
        "region": region,
        "count": len(gold_data),
        "data": gold_data
    }


def albion_get_api_quota_status() -> Dict[str, Any]:
    """
    Retorna o relatório em tempo real do Rate Limiter e saúde de consumo da REST API da AODP.
    
    Permite ao agente saber se pode disparar requisições ou se deve aguardar / utilizar o stream NATS.
    """
    quota = rate_limiter.get_status()
    nats_stat = nats_subscriber.get_status()
    return {
        "aodp_rest_rate_limiter": quota,
        "nats_firehose_stream": nats_stat,
        "recommendation": (
            "Status normal. Você pode realizar consultas REST em lote."
            if quota["health"] == "EXCELENTE" else
            "Consumo elevado ou moderado da API REST! Priorize agrupar chamadas em batching ou consultar via NATS."
        )
    }
