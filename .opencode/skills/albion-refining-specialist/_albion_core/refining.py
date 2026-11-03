"""
Refino industrial: viabilidade por tier/encantamento e cascata completa de sobras.

Substitui o antigo motor Polars (que dependia de um SQLite/Databricks inexistente)
por consultas diretas à API REST da AODP.

Regras oficiais:
- RRR 40% na capital bônus (sem foco) e 53.9% com foco (Premium).
- Nutrição da banca: (ItemValue * 0.1125 / 100) * taxa_por_100.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .calculator import get_tax_rate, SETUP_FEE_RATE
from .http import ROYAL_CITIES, aodp
from .loadout_optimizer import solve_cheapest_loadout
from .metadata import metadata_manager

REFINING_SPECIALTIES = {
    "Bridgewatch": {"resource": "ROCK", "name": "Pedra -> Blocos", "raw_prefix": "ROCK", "refined_prefix": "STONEBLOCK"},
    "Martlock": {"resource": "HIDE", "name": "Pelego -> Couro", "raw_prefix": "HIDE", "refined_prefix": "LEATHER"},
    "Thetford": {"resource": "ORE", "name": "Minério -> Barras", "raw_prefix": "ORE", "refined_prefix": "METALBAR"},
    "Fort Sterling": {"resource": "WOOD", "name": "Madeira -> Tábuas", "raw_prefix": "WOOD", "refined_prefix": "PLANKS"},
    "Lymhurst": {"resource": "FIBER", "name": "Fibra -> Tecidos", "raw_prefix": "FIBER", "refined_prefix": "CLOTH"},
}

RAW_QTY_MAP = {2: 1, 3: 2, 4: 2, 5: 3, 6: 4, 7: 5, 8: 5}
ITEM_VALUE_MAP = {2: 2, 3: 8, 4: 16, 5: 32, 6: 64, 7: 128, 8: 256}
UNIT_WEIGHTS = {2: 0.2, 3: 0.3, 4: 0.5, 5: 0.9, 6: 1.4, 7: 2.0, 8: 2.8}


def _specialty_for(resource_type: str) -> Optional[tuple]:
    for city, spec in REFINING_SPECIALTIES.items():
        if spec["resource"] == resource_type.upper():
            return city, spec
    return None


def _item_ids(tier: int, enchantment: int, raw_prefix: str, refined_prefix: str) -> tuple:
    enc = f"_LEVEL{enchantment}@{enchantment}" if enchantment > 0 else ""
    raw_id = f"T{tier}_{raw_prefix}{enc}"
    refined_id = f"T{tier}_{refined_prefix}{enc}"

    prev_refined_id = None
    if tier > 2:
        if tier == 4 and enchantment > 0:
            prev_refined_id = f"T3_{refined_prefix}"
        else:
            prev_enc = f"_LEVEL{enchantment}@{enchantment}" if (enchantment > 0 and tier > 4) else ""
            prev_refined_id = f"T{tier - 1}_{refined_prefix}{prev_enc}"
    return raw_id, prev_refined_id, refined_id


def _cheapest_sell(rows: List[Dict[str, Any]], item_id: str) -> tuple:
    """Menor sell order válido do item entre as capitais reais -> (preço, cidade)."""
    best = (0, None)
    for row in rows:
        if row.get("item_id") != item_id:
            continue
        price = row.get("sell_price_min") or 0
        city = row.get("city")
        if price > 0 and city in ROYAL_CITIES and (best[0] == 0 or price < best[0]):
            best = (price, city)
    return best


def _city_sell(rows: List[Dict[str, Any]], item_id: str, city: str) -> int:
    for row in rows:
        if row.get("item_id") == item_id and row.get("city") == city:
            return row.get("sell_price_min") or 0
    return 0


def calculate_refining(
    resource_type: str = "ORE",
    tier: int = 5,
    enchantment: int = 0,
    has_focus: bool = False,
    has_premium: bool = False,
    station_fee_per_100: int = 500,
    region: str = "americas",
) -> Dict[str, Any]:
    """Calcula o retorno do refino de um recurso na capital especializada."""
    metadata_manager.ensure_data_loaded()

    match = _specialty_for(resource_type)
    if not match:
        return {"error": f"Recurso '{resource_type}' desconhecido. Use: ORE, WOOD, FIBER, HIDE, ROCK."}
    city, spec = match

    if not 2 <= tier <= 8:
        return {"error": "Tier deve estar entre 2 e 8."}
    if not 0 <= enchantment <= 4:
        return {"error": "Encantamento deve estar entre 0 e 4."}

    raw_id, prev_refined_id, refined_id = _item_ids(
        tier, enchantment, spec["raw_prefix"], spec["refined_prefix"]
    )

    ids = [raw_id, refined_id] + ([prev_refined_id] if prev_refined_id else [])
    rows = aodp.get_prices(ids, locations=ROYAL_CITIES, qualities=[1], region=region)

    raw_price, raw_city = _cheapest_sell(rows, raw_id)
    prev_price = _city_sell(rows, prev_refined_id, city) if prev_refined_id else 0
    sell_price = _city_sell(rows, refined_id, city)

    if raw_price == 0 and sell_price == 0:
        return {
            "error": (
                f"Sem cotações para {raw_id} / {refined_id}. "
                "Verifique o ID, o tier/encantamento ou tente novamente em alguns minutos."
            )
        }

    rrr = 0.539 if has_focus else 0.40
    raw_qty = RAW_QTY_MAP.get(tier, 2)
    item_value = ITEM_VALUE_MAP.get(tier, 16) * (2 ** enchantment)
    nutrition_cost = int(round((item_value * 0.1125 / 100.0) * station_fee_per_100))

    gross_raw_cost = (raw_qty * raw_price) + prev_price
    effective_cost = int(gross_raw_cost * (1.0 - rrr)) + nutrition_cost

    tax_rate = get_tax_rate(has_premium)
    net_revenue = int(round(sell_price * (1.0 - tax_rate - SETUP_FEE_RATE)))
    net_profit = net_revenue - effective_cost
    roi_pct = round((net_profit / effective_cost * 100), 2) if effective_cost > 0 else 0.0

    return {
        "resource": resource_type.upper(),
        "specialized_city": city,
        "tier": f"T{tier}.{enchantment}" if enchantment > 0 else f"T{tier}",
        "raw_material": {
            "item_id": raw_id,
            "name": metadata_manager.get_item_name(raw_id),
            "quantity": raw_qty,
            "price": raw_price,
            "price_city": raw_city,
            "total_cost": raw_qty * raw_price,
        },
        "previous_refined_material": (
            {
                "item_id": prev_refined_id,
                "name": metadata_manager.get_item_name(prev_refined_id),
                "quantity": 1,
                "price": prev_price,
                "price_city": city,
            }
            if prev_refined_id
            else None
        ),
        "refined_product": {
            "item_id": refined_id,
            "name": metadata_manager.get_item_name(refined_id),
            "sell_city": city,
            "sell_price": sell_price,
            "net_revenue": net_revenue,
        },
        "economics": {
            "rrr_pct": round(rrr * 100, 1),
            "has_focus": has_focus,
            "has_premium": has_premium,
            "station_nutrition_cost": nutrition_cost,
            "gross_input_cost": gross_raw_cost,
            "effective_craft_cost": effective_cost,
            "net_profit_per_unit": net_profit,
            "roi_pct": roi_pct,
            "verdict": "🟢 Lucrativo" if roi_pct >= 15 else ("🟡 Margem baixa" if roi_pct > 0 else "🔴 Prejuízo"),
        },
    }


def calculate_cascade_refining(
    resource_type: str = "ORE",
    target_tier: int = 6,
    target_enchantment: int = 1,
    budget: int = 2_000_000,
    has_focus: bool = False,
    has_premium: bool = False,
    station_fee_per_100: int = 500,
    region: str = "americas",
) -> Dict[str, Any]:
    """Compra de matéria-prima, refino em cascata e dimensionamento do kit de carga."""
    base = calculate_refining(
        resource_type=resource_type,
        tier=target_tier,
        enchantment=target_enchantment,
        has_focus=has_focus,
        has_premium=has_premium,
        station_fee_per_100=station_fee_per_100,
        region=region,
    )
    if "error" in base:
        return base

    unit_cost = base["economics"]["effective_craft_cost"] or 100
    units = max(1, budget // unit_cost)
    total_invested = units * unit_cost

    sell_price = base["refined_product"]["sell_price"]
    tax_rate = get_tax_rate(has_premium)
    gross_revenue = units * sell_price
    net_revenue = int(round(gross_revenue * (1.0 - tax_rate - SETUP_FEE_RATE)))
    net_profit = net_revenue - total_invested
    roi_pct = round((net_profit / total_invested * 100), 2) if total_invested > 0 else 0.0

    raw_qty = base["raw_material"]["quantity"] * units
    weight_kg = round(raw_qty * UNIT_WEIGHTS.get(target_tier, 1.0), 1)
    loadout = solve_cheapest_loadout(target_weight_kg=weight_kg, risk_level="SAFE_ONLY")
    kit = loadout.get("cheapest_loadout") or {}

    return {
        "resource": resource_type.upper(),
        "target_tier": f"T{target_tier}.{target_enchantment}" if target_enchantment > 0 else f"T{target_tier}",
        "refining_city": base["specialized_city"],
        "budget_silver": budget,
        "units_produced": units,
        "total_invested": total_invested,
        "gross_revenue": gross_revenue,
        "net_revenue": net_revenue,
        "net_profit": net_profit,
        "roi_pct": roi_pct,
        "cargo": {
            "total_weight_kg": weight_kg,
            "recommended_mount": kit.get("mount_name", "Boi de Transporte T5"),
            "mount_capacity_kg": kit.get("effective_capacity_kg", 1400.0),
            "est_mount_cost": kit.get("total_cost_silver", 55000),
            "recommended_bag": kit.get("bag_name", "Sem Bolsa"),
            "recommended_food": kit.get("food_name", "Sem Comida"),
            "usage_pct": kit.get("usage_pct", 0.0),
            "silver_saved_vs_naive": loadout.get("silver_saved_vs_naive_mount", 0),
        },
        "unit_breakdown": base,
    }
