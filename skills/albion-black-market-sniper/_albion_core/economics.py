"""
Economia: impostos, encantamento, arbitragem e refino.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .calculator import (
    calculate_buy_order_cost,
    calculate_instant_sell_proceeds,
    calculate_sell_order_proceeds,
    calculate_trade_profit,
)
from .http import ROYAL_CITIES, aodp
from .metadata import metadata_manager
from .refining import calculate_cascade_refining, calculate_refining


def calculate_tax_and_fees(
    buy_price: int,
    sell_price: int,
    is_buy_order: bool = True,
    is_sell_order: bool = True,
    has_premium: bool = False,
    quantity: int = 1,
) -> Dict[str, Any]:
    """Custo efetivo de compra, receita líquida e ROI de uma operação."""
    return calculate_trade_profit(
        buy_price=buy_price,
        sell_price=sell_price,
        is_buy_order=is_buy_order,
        is_sell_order=is_sell_order,
        has_premium=has_premium,
        quantity=quantity,
    )


def simulate_enchantment(
    base_item_id: str,
    target_enchantment: int,
    base_item_buy_price: int,
    material_unit_price: int,
    target_item_sell_price: int,
    has_premium: bool = False,
    is_buy_order: bool = True,
    is_sell_order: bool = True,
) -> Dict[str, Any]:
    """Simula o encantamento na Artifact Foundry (.0 -> .1/.2/.3)."""
    metadata_manager.ensure_data_loaded()

    if target_enchantment not in (1, 2, 3):
        return {"error": "target_enchantment deve ser 1, 2 ou 3."}

    clean_base = base_item_id.split("@")[0]
    tier = metadata_manager.get_tier(clean_base)
    slot_type = metadata_manager.get_slot_type(clean_base)
    materials_needed = metadata_manager.get_enchantment_cost(clean_base)

    target_item_id = f"{clean_base}@{target_enchantment}"
    material_name = {1: f"Runas {tier}", 2: f"Almas {tier}", 3: f"Relíquias {tier}"}[target_enchantment]

    base_cost = calculate_buy_order_cost(base_item_buy_price) if is_buy_order else base_item_buy_price
    mat_unit = calculate_buy_order_cost(material_unit_price) if is_buy_order else material_unit_price
    total_materials_cost = materials_needed * mat_unit
    total_craft_cost = base_cost + total_materials_cost

    net_revenue = (
        calculate_sell_order_proceeds(target_item_sell_price, has_premium=has_premium)
        if is_sell_order
        else calculate_instant_sell_proceeds(target_item_sell_price, has_premium=has_premium)
    )

    net_profit = net_revenue - total_craft_cost
    roi_pct = round((net_profit / total_craft_cost * 100), 2) if total_craft_cost > 0 else 0.0

    return {
        "base_item": {
            "item_id": clean_base,
            "name_pt": metadata_manager.get_item_name(clean_base),
            "slot_type": slot_type,
            "buy_price": base_item_buy_price,
            "effective_cost": base_cost,
        },
        "enchantment": {
            "target_level": f".{target_enchantment}",
            "target_item_id": target_item_id,
            "target_name_pt": metadata_manager.get_item_name(target_item_id),
            "material_type": material_name,
            "materials_required": materials_needed,
            "material_unit_price": material_unit_price,
            "total_materials_cost": total_materials_cost,
        },
        "financial_summary": {
            "total_investment": total_craft_cost,
            "gross_sell_price": target_item_sell_price,
            "net_revenue": net_revenue,
            "net_profit": net_profit,
            "roi_pct": roi_pct,
            "has_premium": has_premium,
            "verdict": "🟢 Lucrativo" if roi_pct >= 15.0 else ("🟡 Margem Baixa" if roi_pct > 0 else "🔴 Prejuízo"),
        },
    }


def find_arbitrage(
    item_ids: List[str],
    source_cities: Optional[List[str]] = None,
    target_cities: Optional[List[str]] = None,
    min_roi_pct: float = 12.0,
    has_premium: bool = False,
    region: str = "americas",
    qualities: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Oportunidades de arbitragem entre cidades reais e para o Black Market."""
    if not item_ids:
        return {"error": "item_ids não pode estar vazio.", "opportunities": []}

    qualities = qualities or [1, 2, 3]
    prices = aodp.get_prices(item_ids, region=region, qualities=qualities)
    if not prices:
        return {"opportunities": [], "message": "Nenhuma cotação encontrada na AODP."}

    by_key = {(p.get("item_id"), p.get("quality", 1), p.get("city")): p for p in prices}

    sources = set(source_cities or ROYAL_CITIES)
    targets = set(
        target_cities or ROYAL_CITIES + ["Caerleon", "Black Market"]
    )

    opportunities = []
    for item_id in set(item_ids):
        for quality in qualities:
            best_buy = None
            for city in sources:
                quote = by_key.get((item_id, quality, city))
                if not quote:
                    continue
                price = quote.get("sell_price_min", 0)
                if price > 0 and (best_buy is None or price < best_buy["price"]):
                    best_buy = {"city": city, "price": price}

            if not best_buy:
                continue

            for target_city in targets:
                if target_city == best_buy["city"]:
                    continue
                quote = by_key.get((item_id, quality, target_city))
                if not quote:
                    continue

                is_black_market = target_city == "Black Market"
                target_price = (quote.get("buy_price_max", 0) if is_black_market else quote.get("sell_price_min", 0))
                if target_price <= 0:
                    continue

                trade = calculate_trade_profit(
                    buy_price=best_buy["price"],
                    sell_price=target_price,
                    is_buy_order=False,
                    is_sell_order=not is_black_market,
                    has_premium=has_premium,
                )

                if trade["roi_pct"] < min_roi_pct:
                    continue

                opportunities.append(
                    {
                        "item_id": item_id,
                        "item_name_pt": metadata_manager.get_item_name(item_id),
                        "quality": quality,
                        "buy_city": best_buy["city"],
                        "buy_price": best_buy["price"],
                        "sell_city": target_city,
                        "sell_price": target_price,
                        "is_black_market": is_black_market,
                        "unit_profit": trade["unit_profit"],
                        "roi_pct": trade["roi_pct"],
                        "is_safe_route": best_buy["city"] in ROYAL_CITIES and target_city in ROYAL_CITIES,
                    }
                )

    opportunities.sort(key=lambda row: row["unit_profit"], reverse=True)

    return {
        "total_opportunities": len(opportunities),
        "min_roi_filter": min_roi_pct,
        "has_premium": has_premium,
        "opportunities": opportunities[:30],
    }
