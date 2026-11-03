"""
Curva de Pareto 80/20 do mercado: onde está concentrada a prata diária.

A AODP não expõe um endpoint de "ranking de volume", então a análise é feita
sobre um universo explícito de itens (padrão: recursos refinados T4-T8).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .http import ROYAL_CITIES, aodp, average_price, daily_volume
from .items import resolve_universe
from .metadata import metadata_manager


def pareto_analysis(
    item_ids: Optional[List[str]] = None,
    category: Optional[str] = None,
    tier: Optional[str] = None,
    city: Optional[str] = None,
    days: int = 7,
    top_n: int = 25,
    region: str = "americas",
    max_items: int = 120,
) -> Dict[str, Any]:
    """
    Calcula a concentração de prata diária (preço médio x vendas/dia) no universo informado.

    `item_ids` tem prioridade; se ausente, usa `category`/`tier` sobre o catálogo local.
    """
    metadata_manager.ensure_data_loaded()

    if not item_ids:
        item_ids = resolve_universe(
            category=category or ("Recursos Refinados" if not tier else None),
            tier=tier,
            limit=max_items,
        )

    item_ids = item_ids[:max_items]
    if not item_ids:
        return {"error": "Nenhum item no universo. Informe --items, --category ou --tier."}

    locations = [city] if city else ROYAL_CITIES
    rows = aodp.get_history(item_ids, locations=locations, qualities=[1], days=days, region=region)

    per_item: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        item_id = row.get("item_id")
        data = row.get("data") or []
        avg = average_price(data)
        sales = daily_volume(data)
        if not avg or sales <= 0:
            continue

        entry = per_item.setdefault(
            item_id,
            {
                "item_id": item_id,
                "item_name_pt": metadata_manager.get_item_name(item_id),
                "tier": metadata_manager.get_tier(item_id),
                "category": metadata_manager.get_category_for_item(item_id),
                "daily_sales": 0.0,
                "avg_price": avg,
                "daily_silver": 0,
            },
        )
        entry["daily_sales"] = round(entry["daily_sales"] + sales, 1)
        entry["daily_silver"] += int(avg * sales)

    items = sorted(per_item.values(), key=lambda row: row["daily_silver"], reverse=True)
    total_silver = sum(row["daily_silver"] for row in items) or 1

    cumulative = 0
    for row in items:
        cumulative += row["daily_silver"]
        row["share_pct"] = round(row["daily_silver"] / total_silver * 100, 2)
        row["cum_share_pct"] = round(cumulative / total_silver * 100, 2)

    cutoff_index = next((i for i, row in enumerate(items) if row["cum_share_pct"] >= 80), None)

    return {
        "universe": {
            "category": category,
            "tier": tier,
            "city": city or "todas as capitais reais",
            "items_scanned": len(item_ids),
            "items_with_data": len(items),
            "window_days": days,
            "region": region,
        },
        "total_market_daily_silver": total_silver,
        "pareto_80": {
            "items_needed": (cutoff_index + 1) if cutoff_index is not None else len(items),
            "share_of_universe_pct": (
                round((cutoff_index + 1) / len(items) * 100, 1) if cutoff_index is not None else 100.0
            ),
        },
        "top_items_count": min(top_n, len(items)),
        "items": items[:top_n],
    }
