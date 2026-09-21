"""
Ferramentas MCP para Databricks Unity Catalog (100% Opcional).
"""

from typing import List, Dict, Any, Optional
from ..core.databricks_client import databricks_client


def albion_databricks_status() -> Dict[str, Any]:
    """
    Verifica se a integração com o Databricks Unity Catalog está configurada e disponível no ambiente.

    O Databricks é estritamente opcional. Caso não esteja configurado, o MCP funciona
    normalmente utilizando o Core NATS Firehose e AODP REST API.
    """
    return databricks_client.get_status()


async def albion_databricks_query_gold(
    item_ids: Optional[List[str]] = None,
    location_id: Optional[int] = None,
    limit: int = 25
) -> Dict[str, Any]:
    """
    Consulta features pré-calculadas de histórico de preços diretamente da tabela Gold do Databricks
    (`main.gold.history_features`).

    ATENÇÃO: Requer configuração prévia de DATABRICKS_HOST, DATABRICKS_TOKEN e DATABRICKS_WAREHOUSE_ID.
    Se o Databricks não estiver configurado, retorna uma mensagem explicativa sem erros.

    Parâmetros:
    - item_ids: Lista opcional de IDs de itens para filtrar.
    - location_id: ID numérico da praça (ex: 1002 para Lymhurst, 3003 para Black Market).
    - limit: Limite de linhas retornadas (padrão: 25).
    """
    if not databricks_client.is_configured():
        return {
            "configured": False,
            "message": (
                "Databricks não configurado no ambiente (.env). "
                "Esta ferramenta é opcional. Utilize 'albion_get_current_prices' ou "
                "'albion_nats_get_live_orders' para dados do Albion Online."
            )
        }

    return await databricks_client.query_gold_features(
        item_ids=item_ids,
        location_id=location_id,
        limit=limit
    )
