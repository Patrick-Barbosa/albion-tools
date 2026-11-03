"""
Matemática determinística e travas anti-alucinação.

Inclui breakeven fiscal exato, auditoria de ordens fantasmas, alocação inteira de
orçamento, valor esperado de reroll de qualidade, física de carga e transmutação.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .calculator import (
    allocate_portfolio_budget,
    calculate_breakeven_prices,
    calculate_loadout_capacity,
    calculate_quality_reroll_ev,
)
from .http import ROYAL_CITIES, aodp, average_price, daily_volume
from .loadout_optimizer import (
    BAG_LOAD_MAP,
    BOOTS_PASSIVE_MAP,
    MOUNTS_LIST,
    PIE_LOAD_MAP,
    solve_cheapest_loadout,
)
from .metadata import metadata_manager


def calculate_breakeven_price(
    buy_price: int,
    is_buy_order: bool = True,
    has_premium: bool = False,
    price_updates_buy: int = 0,
    price_updates_sell: int = 0,
    target_roi_pct: float = 0.0,
) -> Dict[str, Any]:
    """Preço mínimo de venda para empatar (ou atingir a margem alvo), com taxas e renovações."""
    return calculate_breakeven_prices(
        buy_price=buy_price,
        is_buy_order=is_buy_order,
        has_premium=has_premium,
        price_updates_buy=price_updates_buy,
        price_updates_sell=price_updates_sell,
        target_roi_pct=target_roi_pct,
    )


def audit_quote(
    item_id: str,
    city: str,
    quote_price: Optional[int] = None,
    quote_type: str = "sell_order",
    age_seconds: Optional[int] = None,
    region: str = "americas",
    days: int = 7,
) -> Dict[str, Any]:
    """
    Audita uma cotação contra a média histórica real da AODP.

    Se `quote_price` não for informado, busca a cotação atual na própria AODP.
    """
    metadata_manager.ensure_data_loaded()

    rows = aodp.get_history([item_id], locations=[city], qualities=[1], days=days, region=region)
    history = rows[0].get("data") if rows else []

    avg_hist = average_price(history or []) or 0
    sales = daily_volume(history or [])

    if quote_price is None:
        prices = aodp.get_prices([item_id], locations=[city], qualities=[1], region=region)
        if prices:
            row = prices[0]
            quote_price = row.get("sell_price_min" if quote_type == "sell_order" else "buy_price_max") or 0
            date_str = row.get("sell_price_min_date" if quote_type == "sell_order" else "buy_price_max_date")
            if age_seconds is None and date_str:
                age_seconds = _age_seconds(date_str)
        else:
            quote_price = 0

    reference = avg_hist if avg_hist > 0 else (quote_price or 0)
    deviation = round((quote_price - reference) / reference * 100, 1) if reference > 0 else 0.0

    if age_seconds is None:
        freshness, freshness_label = "UNKNOWN", "⚪ Idade da cotação desconhecida."
    elif age_seconds <= 120:
        freshness, freshness_label = "LIVE_CONFIRMED", "🟢 Dados 100% ao vivo (< 2 min)"
    elif age_seconds <= 600:
        freshness, freshness_label = "ACCEPTABLE", "🟡 Dados recentes (< 10 min)"
    elif age_seconds <= 86400:
        freshness, freshness_label = "STALE_WARNING", "⚠️ Dados antigos (> 10 min). A ordem pode não existir mais."
    else:
        freshness, freshness_label = "EXPIRED", "🔴 Dados muito antigos (> 24h). Não use para decisão financeira."

    if deviation > 60.0:
        phantom, phantom_label = "PHANTOM_SUSPECT", "🔴 Preço >60% acima da média histórica: suspeita de ordem fantasma."
    elif deviation < -60.0:
        phantom, phantom_label = "DUMP_SUSPECT", "🔴 Preço >60% abaixo da média: suspeita de despejo anormal."
    elif deviation > 30.0:
        phantom, phantom_label = "SPIKE_DEMAND", "🟡 Demanda aquecida (+30% a +60% sobre a média)."
    else:
        phantom, phantom_label = "NORMAL", "🟢 Preço dentro do padrão histórico (±30%)."

    safe_bid_cap = int(round(reference * 1.15))

    return {
        "item_id": item_id,
        "item_name_pt": metadata_manager.get_item_name(item_id),
        "city": city,
        "quote_type": quote_type,
        "quote_price": quote_price,
        "historical_avg_price": avg_hist,
        "historical_daily_sales": sales,
        "window_days": days,
        "deviation_from_avg_pct": deviation,
        "freshness": {"status": freshness, "label": freshness_label, "age_seconds": age_seconds},
        "phantom_audit": {
            "status": phantom,
            "label": phantom_label,
            "is_reliable": phantom in ("NORMAL", "SPIKE_DEMAND") and freshness != "EXPIRED",
        },
        "safe_guardrails": {
            "safe_max_bid_silver": safe_bid_cap,
            "safe_sell_cap_silver": int(round(reference * 1.15)),
            "liquidity_gate_ok": sales >= 1.0,
            "recommendation": (
                f"Não pague acima de {safe_bid_cap:,} 🪙 (teto +15% sobre a média histórica).".replace(",", ".")
            ),
        },
    }


def _age_seconds(date_str: str) -> Optional[int]:
    from datetime import datetime, timezone

    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(date_str.split("+")[0].split("Z")[0], fmt).replace(tzinfo=timezone.utc)
            return int((datetime.now(timezone.utc) - parsed).total_seconds())
        except ValueError:
            continue
    return None


def allocate_budget(
    budget: int,
    candidate_items: List[Dict[str, Any]],
    max_items_count: int = 5,
    has_premium: bool = False,
    max_budget_per_item_pct: float = 40.0,
) -> Dict[str, Any]:
    """Knapsack inteiro com setup fee reservada e diversificação por item."""
    return allocate_portfolio_budget(
        budget=budget,
        candidates=candidate_items,
        max_items=max_items_count,
        has_premium=has_premium,
        max_capital_per_item_pct=max_budget_per_item_pct,
    )


def simulate_quality_reroll(
    item_id: str,
    current_quality: int = 1,
    target_quality: int = 4,
) -> Dict[str, Any]:
    """Valor esperado e pior caso (95%) do reroll de qualidade na Repair Station."""
    metadata_manager.ensure_data_loaded()
    clean_id = item_id.split("@")[0]
    tier_str = metadata_manager.get_tier(clean_id)
    tier = int(tier_str.replace("T", "")) if "T" in tier_str else 4

    result = calculate_quality_reroll_ev(
        tier=tier,
        slot_type=metadata_manager.get_slot_type(clean_id),
        current_quality=current_quality,
        target_quality=target_quality,
    )
    result["item_id"] = item_id
    result["item_name_pt"] = metadata_manager.get_item_name(item_id)
    return result


def calculate_exact_loadout_capacity(
    items_list: List[Dict[str, Any]],
    mount_id: str = "OX_T5",
    bag_id: str = "T5.0",
    pie_id: str = "T7_PORK",
    boots_passive_id: str = "COURIER_STANDARD",
) -> Dict[str, Any]:
    """Valida peso de carga contra a capacidade exata do kit (montaria + bolsa + torta + bota)."""
    mount = next((m for m in MOUNTS_LIST if m["id"] == mount_id), MOUNTS_LIST[2])
    bag = BAG_LOAD_MAP.get(bag_id, BAG_LOAD_MAP["T5.0"])
    pie = PIE_LOAD_MAP.get(pie_id, PIE_LOAD_MAP["T7_PORK"])
    boots = BOOTS_PASSIVE_MAP.get(boots_passive_id, BOOTS_PASSIVE_MAP["COURIER_STANDARD"])

    result = calculate_loadout_capacity(
        items_list=items_list,
        mount_capacity_kg=mount["capacity_kg"],
        bag_bonus_kg=bag["bonus_kg"],
        pie_bonus_pct=pie["bonus_pct"],
        boots_bonus_pct=boots["bonus_pct"],
    )

    result["equipped_kit"] = {
        "mount_name": mount["name"],
        "bag_name": bag["name"],
        "pie_name": pie["name"],
        "boots_passive_name": boots["name"],
    }

    cargo_weight = result.get("total_cargo_weight_kg", 0.0)
    if cargo_weight > 0:
        opt = solve_cheapest_loadout(target_weight_kg=cargo_weight, current_mount_id=mount.get("id"))
        result["solver_recommendation"] = {
            "is_current_kit_sufficient": result.get("capacity_usage_pct", 0.0) <= 100.0,
            "cheapest_loadout": opt.get("cheapest_loadout"),
            "silver_saved_vs_naive": opt.get("silver_saved_vs_naive_mount", 0),
        }

    return result


def calculate_transmutation_cost(
    resource_type: str = "ORE",
    from_tier: int = 4,
    to_tier: int = 5,
    quantity: int = 100,
    from_item_buy_price: int = 150,
    to_item_market_price: int = 600,
) -> Dict[str, Any]:
    """Transmutação no Transmutador municipal vs compra direta do item pronto."""
    resource = resource_type.upper().strip()

    if resource in ("HEART", "FACTION_HEART", "CORACAO", "CORAÇÃO"):
        step_fee = 5780
        path_label = "Coração Sombrio -> Coração de Cidade Real"
    else:
        fees = {(4, 5): 225, (5, 6): 580, (6, 7): 1650, (7, 8): 4800}
        step_fee = fees.get((from_tier, to_tier))
        if not step_fee:
            step_fee = sum(fees.get((t, t + 1), 500 * t) for t in range(from_tier, to_tier))
        path_label = f"T{from_tier} -> T{to_tier}"

    unit_transmute_cost = from_item_buy_price + step_fee
    total_transmute_cost = unit_transmute_cost * quantity
    total_market_cost = to_item_market_price * quantity

    difference = total_market_cost - total_transmute_cost
    worth = difference > 0

    return {
        "resource": resource,
        "transmutation_path": path_label,
        "quantity": quantity,
        "input_tier_unit_cost": from_item_buy_price,
        "system_silver_fee_per_unit": step_fee,
        "total_transmute_cost_per_unit": unit_transmute_cost,
        "total_transmute_cost_batch": total_transmute_cost,
        "market_price_to_buy_ready_unit": to_item_market_price,
        "market_cost_to_buy_ready_batch": total_market_cost,
        "silver_saved_by_transmuting": difference if worth else 0,
        "silver_lost_by_transmuting": abs(difference) if not worth else 0,
        "is_transmutation_cheaper": worth,
        "verdict": (
            f"🟢 Transmutar é MAIS BARATO: economiza {difference:,} 🪙 no lote."
            if worth
            else f"🔴 NÃO TRANSMUTE: comprar pronto é mais barato em {abs(difference):,} 🪙."
        ).replace(",", "."),
    }
