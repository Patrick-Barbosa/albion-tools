"""
Consultas de mercado: cotações atuais, histórico, ouro e quota da API.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .http import aodp, average_price, daily_volume
from .metadata import QUALITY_NAMES, metadata_manager


def current_prices(
    item_ids: List[str],
    locations: Optional[List[str]] = None,
    qualities: Optional[List[int]] = None,
    region: str = "americas",
) -> Dict[str, Any]:
    """Cotações atuais (menor sell order / maior buy order) enriquecidas com nomes PT-BR."""
    if not item_ids:
        return {"error": "item_ids não pode estar vazio.", "quotes": []}

    rows = aodp.get_prices(item_ids, locations, qualities, region)

    quotes = []
    for row in rows:
        item_id = row.get("item_id")
        quality = row.get("quality", 1)
        quotes.append(
            {
                "item_id": item_id,
                "item_name_pt": metadata_manager.get_item_name(item_id),
                "city": row.get("city"),
                "quality": quality,
                "quality_name": QUALITY_NAMES.get(quality, f"Q{quality}"),
                "sell_price_min": row.get("sell_price_min", 0),
                "sell_price_min_date": row.get("sell_price_min_date"),
                "buy_price_max": row.get("buy_price_max", 0),
                "buy_price_max_date": row.get("buy_price_max_date"),
            }
        )

    return {
        "region": region,
        "total_quotes": len(quotes),
        "quota_health": aodp.quota()["health"],
        "remaining_calls_1m": aodp.quota()["window_1_minute"]["remaining"],
        "quotes": quotes,
    }


def price_history(
    item_ids: List[str],
    locations: Optional[List[str]] = None,
    qualities: Optional[List[int]] = None,
    days: int = 7,
    time_scale: int = 24,
    region: str = "americas",
) -> Dict[str, Any]:
    """Histórico de transações com preço médio ponderado e volume diário por item/cidade."""
    if not item_ids:
        return {"error": "item_ids não pode estar vazio.", "items": []}

    rows = aodp.get_history(item_ids, locations, qualities, time_scale, days, region)

    items = []
    for row in rows:
        data = row.get("data") or []
        avg = average_price(data)
        items.append(
            {
                "item_id": row.get("item_id"),
                "item_name_pt": metadata_manager.get_item_name(row.get("item_id")),
                "city": row.get("location"),
                "quality": row.get("quality", 1),
                "avg_price": avg or 0,
                "avg_daily_sales": daily_volume(data),
                "total_sold": sum(point.get("item_count") or 0 for point in data),
                "days_with_data": len({(p.get("timestamp_date") or p.get("timestamp")) for p in data}),
                "window_days": days,
            }
        )

    return {"region": region, "window_days": days, "items": items}


def gold_prices(count: int = 24, region: str = "americas") -> Dict[str, Any]:
    """Histórico recente do preço do ouro em prata."""
    rows = aodp.get_gold(count=count, region=region)
    prices = [
        {"timestamp": row.get("timestamp"), "price": row.get("price")}
        for row in rows
        if row.get("price")
    ]
    prices.sort(key=lambda r: r["timestamp"] or 0)

    if not prices:
        return {"region": region, "count": 0, "prices": []}

    values = [p["price"] for p in prices]
    return {
        "region": region,
        "count": len(prices),
        "latest_price": values[-1],
        "min_price": min(values),
        "max_price": max(values),
        "avg_price": round(sum(values) / len(values)),
        "prices": prices,
    }


def quota_status() -> Dict[str, Any]:
    """Saúde do rate limiter local (não é a quota global do servidor da AODP)."""
    return aodp.quota()


def quote_map(rows: List[Dict[str, Any]]) -> Dict[tuple, Dict[str, Any]]:
    """Indexa cotações por (item_id, qualidade, cidade)."""
    index: Dict[tuple, Dict[str, Any]] = {}
    for row in rows:
        index[(row.get("item_id"), row.get("quality", 1), row.get("city"))] = row
    return index


def history_lookup(
    item_id: str,
    city: str,
    days: int = 7,
    region: str = "americas",
) -> Dict[str, Any]:
    """Preço médio histórico e volume diário de um item em uma cidade."""
    rows = aodp.get_history([item_id], locations=[city], qualities=[1], days=days, region=region)
    if not rows:
        return {"avg_price": 0, "avg_daily_sales": 0.0, "found": False}

    data = rows[0].get("data") or []
    return {
        "avg_price": average_price(data) or 0,
        "avg_daily_sales": daily_volume(data),
        "found": bool(data),
    }
