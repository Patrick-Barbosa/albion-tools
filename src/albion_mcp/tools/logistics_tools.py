"""
Ferramentas MCP para Logística Universal de Carga e Dimensionamento de Montarias.
"""

from typing import Dict, Any, Optional, List
from ..core.loadout_optimizer import solve_cheapest_loadout, calculate_effective_capacity


def albion_optimize_loadout_capacity(
    target_weight_kg: float = 0.0,
    items_list: Optional[List[Dict[str, Any]]] = None,
    current_mount: Optional[str] = None,
    risk_level: str = "SAFE_ONLY",
    max_budget: Optional[int] = None
) -> Dict[str, Any]:
    """
    Resolve a combinação mais barata de Montaria + Bolsa + Torta + Bota para carregar qualquer peso no Albion Online.

    Útil universalmente para:
    - Transporte de fardos de facção (125 kg, 668 kg, 1.623 kg).
    - Transporte industrial de refino (madeira, minério, fibra, pelego, pedras).
    - Arbitragem comercial pesada entre capitais.
    - Exportação de lotes de equipamentos para o Black Market.

    Parâmetros:
    - target_weight_kg: Peso total a ser transportado em quilogramas (ex: 668.0 para 7 corações, 1623.0 para 15).
    - items_list: Lista opcional de itens com peso e quantidade: [{'item_id': ..., 'weight_unit_kg': 0.9, 'quantity': 1500}].
      Se informada, o peso total é calculado automaticamente somando os itens.
    - current_mount: Montaria que o jogador já possui (ex: 'T5_BOAR', 'T4_OX', 'T5_OX', 'T7_BOAR').
    - risk_level: 'SAFE_ONLY' (permite qualquer montaria) ou 'ALLOW_RED_ZONE' (exige montarias com carga passiva anti-gank).
    - max_budget: Orçamento máximo em prata que o jogador aceita gastar em equipamentos adicionais (opcional).
    """
    effective_weight = float(target_weight_kg)
    if items_list:
        items_weight = sum(float(item.get("weight_unit_kg", 0.0)) * int(item.get("quantity", 1)) for item in items_list)
        if effective_weight <= 0.0 or items_weight > effective_weight:
            effective_weight = items_weight

    result = solve_cheapest_loadout(
        target_weight_kg=effective_weight,
        current_mount_id=current_mount,
        risk_level=risk_level,
        max_budget=max_budget
    )
    if items_list:
        result["items_count"] = len(items_list)
        result["items_computed_weight_kg"] = round(effective_weight, 2)
    return result

