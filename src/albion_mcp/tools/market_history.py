"""
Ferramentas MCP para consulta de histórico de preços, volume e curva de Pareto.
"""

from typing import List, Dict, Any, Optional
from ..core.aodp_client import aodp_client
from ..core.polars_analytics import analytics_engine
from ..core.metadata import metadata_manager, QUALITY_NAMES


async def albion_get_price_history(
    item_ids: List[str],
    locations: Optional[List[str]] = None,
    qualities: Optional[List[int]] = None,
    time_scale: int = 24,
    region: str = "americas"
) -> Dict[str, Any]:
    """
    Consulta o histórico de volume e preços médios diários negociados (Sell Orders) via API AODP.

    IMPORTANTE - RESSALVAS DE LIMITES BAIXOS DA API:
    - Esta consulta consome chamadas REST com cache de 30 minutos em memória.
    - Sempre envie listas de itens em lote (`item_ids`) em vez de chamadas individuais.

    Parâmetros:
    - item_ids: Lista de IDs dos itens (ex: ['T4_BAG', 'T6_MAIN_SWORD@1']).
    - locations: Cidades desejadas (ex: ['Lymhurst', 'Bridgewatch', 'Thetford', 'Martlock', 'Fort Sterling']).
    - qualities: Lista de qualidades (padrão: [1]).
    - time_scale: Escala temporal em horas (24 para agregação diária, 1 para horária).
    - region: Região do servidor ('americas', 'asia', 'europe').
    """
    if not item_ids:
        return {"error": "item_ids não pode estar vazio.", "history": []}

    raw_history = await aodp_client.get_price_history(
        item_ids=item_ids,
        locations=locations,
        qualities=qualities,
        time_scale=time_scale,
        region=region
    )

    enriched = []
    for entry in raw_history:
        i_id = entry.get("item_id")
        q = entry.get("quality", 1)
        loc = entry.get("location")
        data_points = entry.get("data", [])

        clean_points = []
        for dp in data_points:
            ts = dp.get("timestamp")
            avg_p = dp.get("avg_price", 0)
            cnt = dp.get("item_count", 0)
            if ts and avg_p > 0:
                clean_points.append({
                    "date": ts[:10],
                    "avg_price": avg_p,
                    "item_count": cnt
                })

        enriched.append({
            "item_id": i_id,
            "item_name_pt": metadata_manager.get_item_name(i_id),
            "city": loc,
            "quality": q,
            "quality_name": QUALITY_NAMES.get(q, f"Q{q}"),
            "time_scale_hours": time_scale,
            "total_data_points": len(clean_points),
            "data": clean_points
        })

    return {
        "region": region,
        "total_series": len(enriched),
        "history": enriched
    }


def albion_get_market_pareto(top_n: int = 25) -> Dict[str, Any]:
    """
    Retorna a curva de Pareto (80/20) e classificação ABC dos itens mais movimentados em prata diária.

    Calculado em memória via motor Polars a partir do banco de dados histórico local,
    sem nenhum consumo da REST API.
    
    Parâmetros:
    - top_n: Quantidade de itens do topo a retornar (padrão: 25).
    """
    return analytics_engine.get_pareto_analysis(top_n=top_n)
