"""
Motor de Cálculo Financeiro e Regras Econômicas Oficiais do Albion Online.

Regras consolidadas conforme BUSINESS_RULES.md:
- Setup Fee (Taxa de Postagem de Ordens): 2.5% não reembolsável
- Transaction Tax (Taxa de Venda Final): 4.0% (Com Premium) / 8.0% (Sem Premium)
- Instant Buy: Paga estritamente o valor do vendedor (sem taxa de postagem)
- Instant Sell (Venda Direta em Buy Order / Black Market): Vendedor paga apenas taxa de venda (4% / 8%)
- Quantidade de insumos para encantamento por slot (múltiplos de 96):
  * Armas 2H: 384
  * Armas 1H: 288
  * Armaduras de Peito e Bolsas: 192
  * Elmos, Botas, Secundários e Capas: 96
"""

from typing import Dict, Any

PREMIUM_TAX = 0.04
NON_PREMIUM_TAX = 0.08
SETUP_FEE_RATE = 0.025

# Múltiplos de insumos por slot
ENCHANT_SLOT_COSTS = {
    "2H_WEAPON": 384,
    "1H_WEAPON": 288,
    "ARMOR": 192,
    "BAG": 192,
    "HELMET": 96,
    "BOOTS": 96,
    "OFFHAND": 96,
    "CAPE": 96,
}


def get_tax_rate(has_premium: bool = False) -> float:
    """Retorna a taxa de transação de venda (4% com premium, 8% sem premium)."""
    return PREMIUM_TAX if has_premium else NON_PREMIUM_TAX


def calculate_buy_order_cost(bid_price: int, price_updates: int = 0) -> int:
    """
    Calcula o custo efetivo de compra via Buy Order:
    custo = bid * (1 + 0.025 * (1 + price_updates))
    """
    fee_multiplier = 1.0 + SETUP_FEE_RATE * (1 + price_updates)
    return int(round(bid_price * fee_multiplier))


def calculate_sell_order_proceeds(sell_price: int, has_premium: bool = False, price_updates: int = 0) -> int:
    """
    Calcula a receita líquida recebida ao vender via Sell Order:
    receita = sell_price * (1 - tax - 0.025 * (1 + price_updates))
    """
    tax = get_tax_rate(has_premium)
    setup = SETUP_FEE_RATE * (1 + price_updates)
    net_factor = max(0.0, 1.0 - tax - setup)
    return int(round(sell_price * net_factor))


def calculate_instant_sell_proceeds(buyer_price: int, has_premium: bool = False) -> int:
    """
    Calcula a receita líquida recebida ao vender diretamente para uma Buy Order (ex: Black Market):
    receita = buyer_price * (1 - tax)
    Não há cobrança de Setup Fee.
    """
    tax = get_tax_rate(has_premium)
    return int(round(buyer_price * (1.0 - tax)))


def calculate_trade_profit(
    buy_price: int,
    sell_price: int,
    is_buy_order: bool = True,
    is_sell_order: bool = True,
    has_premium: bool = False,
    quantity: int = 1
) -> Dict[str, Any]:
    """
    Calcula o resultado financeiro detalhado de uma operação de compra e venda.
    """
    unit_cost = calculate_buy_order_cost(buy_price) if is_buy_order else buy_price
    unit_revenue = (
        calculate_sell_order_proceeds(sell_price, has_premium=has_premium)
        if is_sell_order else
        calculate_instant_sell_proceeds(sell_price, has_premium=has_premium)
    )

    total_cost = unit_cost * quantity
    total_revenue = unit_revenue * quantity
    net_profit = total_revenue - total_cost
    roi_pct = round((net_profit / total_cost * 100), 2) if total_cost > 0 else 0.0

    return {
        "unit_buy_price": buy_price,
        "unit_cost_effective": unit_cost,
        "unit_sell_price": sell_price,
        "unit_revenue_effective": unit_revenue,
        "unit_profit": unit_revenue - unit_cost,
        "quantity": quantity,
        "total_invested": total_cost,
        "total_revenue": total_revenue,
        "net_profit": net_profit,
        "roi_pct": roi_pct,
        "has_premium": has_premium,
        "is_buy_order": is_buy_order,
        "is_sell_order": is_sell_order,
    }


def calculate_breakeven_prices(
    buy_price: int,
    is_buy_order: bool = True,
    has_premium: bool = False,
    price_updates_buy: int = 0,
    price_updates_sell: int = 0,
    target_roi_pct: float = 0.0
) -> Dict[str, Any]:
    """
    Calcula os preços exatos de ponto de equilíbrio (Break-even) e metas de ROI,
    invertendo rigorosamente as equações fiscais do jogo com setup fees acumuladas.
    """
    import math

    effective_cost = calculate_buy_order_cost(buy_price, price_updates_buy) if is_buy_order else buy_price
    target_net_revenue = int(round(effective_cost * (1.0 + max(0.0, target_roi_pct) / 100.0)))

    tax = get_tax_rate(has_premium)
    setup_factor_sell = SETUP_FEE_RATE * (1 + price_updates_sell)
    net_factor_sell_order = 1.0 - tax - setup_factor_sell

    min_sell_order_price = int(math.ceil(target_net_revenue / net_factor_sell_order)) if net_factor_sell_order > 0 else 0
    net_factor_instant = 1.0 - tax
    min_instant_sell_price = int(math.ceil(target_net_revenue / net_factor_instant)) if net_factor_instant > 0 else 0

    # Quantas renovações de venda a ordem aguenta no preço de venda antes de entrar no vermelho
    max_sell_updates = 0
    if min_sell_order_price > 0:
        base_net = min_sell_order_price * (1.0 - tax - SETUP_FEE_RATE)
        margin_left = base_net - effective_cost
        fee_per_update = min_sell_order_price * SETUP_FEE_RATE
        if margin_left > 0 and fee_per_update > 0:
            max_sell_updates = int(margin_left // fee_per_update)

    return {
        "unit_buy_price": buy_price,
        "effective_cost": effective_cost,
        "is_buy_order": is_buy_order,
        "price_updates_buy": price_updates_buy,
        "price_updates_sell": price_updates_sell,
        "target_roi_pct": target_roi_pct,
        "target_net_revenue": target_net_revenue,
        "min_sell_order_price": min_sell_order_price,
        "min_instant_sell_price": min_instant_sell_price,
        "tax_rate_pct": round(tax * 100, 1),
        "setup_fee_sell_pct": round(setup_factor_sell * 100, 2),
        "max_sell_order_updates_before_loss": max_sell_updates,
        "has_premium": has_premium,
    }


def calculate_quality_reroll_ev(
    tier: int,
    slot_type: str = "ARMOR",
    current_quality: int = 1,
    target_quality: int = 4
) -> Dict[str, Any]:
    """
    Calcula o Custo Esperado (Expected Value - EV) e intervalo de pior caso
    para tentativas de reroll de qualidade na Repair Station.
    """
    import math

    # Multiplicadores de Item Value por Tier e Slot
    TIER_BASE_IV = {2: 2, 3: 8, 4: 16, 5: 32, 6: 64, 7: 128, 8: 256}
    SLOT_MULTIPLIERS = {
        "2H_WEAPON": 4.0,
        "1H_WEAPON": 3.0,
        "ARMOR": 2.0,
        "BAG": 2.0,
        "HELMET": 1.0,
        "BOOTS": 1.0,
        "OFFHAND": 1.0,
        "CAPE": 1.0,
    }

    base_iv = TIER_BASE_IV.get(tier, 16)
    slot_mult = SLOT_MULTIPLIERS.get(slot_type.upper(), 2.0)
    item_value = int(round(base_iv * slot_mult))

    # Custo por tentativa na oficina de reparo: aprox. 1.5 * IV em prata
    cost_per_attempt = max(10, int(round(item_value * 1.5)))

    # Probabilidade de sucesso por nível de qualidade alvo:
    # 1 -> 2 (Normal -> Bom): 40%
    # 2 -> 3 (Bom -> Notável): 30%
    # 3 -> 4 (Notável -> Excelente): 10%
    # 4 -> 5 (Excelente -> Obra-prima): 1%
    STAGE_PROBS = {
        2: 0.40,
        3: 0.30,
        4: 0.10,
        5: 0.01,
    }

    if target_quality <= current_quality:
        return {
            "error": "target_quality deve ser maior que current_quality.",
            "expected_total_cost": 0
        }

    total_ev_attempts = 0.0
    stage_breakdown = []

    for q in range(current_quality + 1, target_quality + 1):
        p = STAGE_PROBS.get(q, 0.10)
        ev_attempts = 1.0 / p
        total_ev_attempts += ev_attempts
        # Pior caso 95% de confiança: 1 - (1-p)^N = 0.95 => N = ln(0.05) / ln(1-p)
        worst_case_95 = int(math.ceil(math.log(0.05) / math.log(1.0 - p)))

        stage_breakdown.append({
            "stage": f"Q{q-1} -> Q{q}",
            "success_probability_pct": round(p * 100, 1),
            "expected_attempts": round(ev_attempts, 1),
            "worst_case_attempts_95pct": worst_case_95,
            "stage_ev_cost": int(round(ev_attempts * cost_per_attempt)),
            "stage_worst_cost_95pct": worst_case_95 * cost_per_attempt
        })

    expected_total_cost = int(round(total_ev_attempts * cost_per_attempt))
    worst_case_total_cost = sum(s["stage_worst_cost_95pct"] for s in stage_breakdown)

    return {
        "tier": f"T{tier}",
        "slot_type": slot_type,
        "item_value": item_value,
        "cost_per_attempt_silver": cost_per_attempt,
        "current_quality": current_quality,
        "target_quality": target_quality,
        "total_expected_attempts": round(total_ev_attempts, 1),
        "expected_total_cost_silver": expected_total_cost,
        "worst_case_95pct_cost_silver": worst_case_total_cost,
        "stages": stage_breakdown,
        "decision_rule": (
            f"Se a diferença de preço de mercado entre Q{current_quality} e Q{target_quality} "
            f"for MAIOR que {expected_total_cost:,} 🪙, o reroll possui Valor Esperado Positivo (EV+). "
            f"Caso contrário, compre o item já na qualidade desejada."
        ).replace(",", ".")
    }


def calculate_loadout_capacity(
    items_list: list[dict],
    mount_capacity_kg: float = 400.0,
    bag_bonus_kg: float = 141.0,
    pie_bonus_pct: float = 30.0,
    boots_bonus_pct: float = 14.0
) -> Dict[str, Any]:
    """
    Calcula a capacidade exata de carga e o diagnóstico de sobrecarga in-game.
    Fórmula oficial:
    Capacidade = (Montaria + Bolsa + 50) * (1 + Torta/100) * (1 + Bota/100)
    """
    base_kg = mount_capacity_kg + bag_bonus_kg + 50.0
    pie_mult = 1.0 + (pie_bonus_pct / 100.0)
    boots_mult = 1.0 + (boots_bonus_pct / 100.0)
    total_capacity_kg = round(base_kg * pie_mult * boots_mult, 1)

    total_cargo_weight_kg = 0.0
    for it in items_list:
        weight_unit = float(it.get("weight_unit_kg", 0.5))
        qty = int(it.get("quantity", 1))
        total_cargo_weight_kg += weight_unit * qty

    total_cargo_weight_kg = round(total_cargo_weight_kg, 1)

    usage_pct = round((total_cargo_weight_kg / total_capacity_kg * 100), 1) if total_capacity_kg > 0 else 999.0

    if usage_pct <= 100.0:
        status = "SAFE_SPRINT"
        status_label = "🟢 100% Seguro (Galope normal e corrida liberada)"
    elif usage_pct < 200.0:
        status = "SLOW_MOUNT"
        status_label = "🟡 Alerta de Sobrecarga (Velocidade reduzida ao ser desmontado por gankers)"
    else:
        status = "CRITICAL_IMMOBILE"
        status_label = "🔴 Sobrecarga Crítica (≥ 200% - Impossibilitado de se mover ou montar)"

    num_trips_needed = 1 if usage_pct <= 100.0 else int(total_cargo_weight_kg // total_capacity_kg) + 1

    return {
        "total_capacity_kg": total_capacity_kg,
        "total_cargo_weight_kg": total_cargo_weight_kg,
        "capacity_usage_pct": usage_pct,
        "remaining_capacity_kg": max(0.0, round(total_capacity_kg - total_cargo_weight_kg, 1)),
        "status": status,
        "status_label": status_label,
        "num_trips_needed": num_trips_needed,
        "loadout_parameters": {
            "mount_base_capacity_kg": mount_capacity_kg,
            "bag_bonus_kg": bag_bonus_kg,
            "player_base_kg": 50.0,
            "pie_bonus_pct": pie_bonus_pct,
            "boots_bonus_pct": boots_bonus_pct
        }
    }


def allocate_portfolio_budget(
    budget: int,
    candidates: list[dict],
    max_items: int = 5,
    has_premium: bool = False,
    max_capital_per_item_pct: float = 40.0
) -> Dict[str, Any]:
    """
    Algoritmo determinístico de alocação de carteira inteira (Knapsack Bounded).
    Garante que nenhuma unidade seja fracionária e reserva rigorosamente os 2.5% de setup fee.
    """
    if budget <= 0 or not candidates:
        return {"error": "Orçamento ou lista de candidatos inválida.", "allocations": []}

    max_capital_per_item = int(round(budget * (max_capital_per_item_pct / 100.0)))
    tax = get_tax_rate(has_premium)

    # Ordena candidatos por ROI líquido descrescente
    sorted_candidates = []
    for c in candidates:
        buy_p = int(c.get("buy_price", 0))
        sell_p = int(c.get("sell_price", 0))
        is_buy_order = c.get("is_buy_order", True)
        is_sell_order = c.get("is_sell_order", True)

        if buy_p <= 0 or sell_p <= 0:
            continue

        trade = calculate_trade_profit(
            buy_price=buy_p,
            sell_price=sell_p,
            is_buy_order=is_buy_order,
            is_sell_order=is_sell_order,
            has_premium=has_premium
        )
        c_copy = dict(c)
        c_copy["trade_metrics"] = trade
        c_copy["roi_pct"] = trade["roi_pct"]
        sorted_candidates.append(c_copy)

    sorted_candidates.sort(key=lambda x: x["roi_pct"], reverse=True)

    allocations = []
    remaining_budget = budget
    total_invested = 0
    total_projected_net_profit = 0

    for cand in sorted_candidates[:max_items]:
        if remaining_budget <= 0:
            break

        cost_per_unit = cand["trade_metrics"]["unit_cost_effective"]
        unit_profit = cand["trade_metrics"]["unit_profit"]

        if cost_per_unit <= 0 or unit_profit <= 0:
            continue

        # Teto de capital para este item
        budget_for_this = min(remaining_budget, max_capital_per_item)
        max_units = int(budget_for_this // cost_per_unit)

        # Restrição opcional de volume diário
        daily_vol = cand.get("daily_volume")
        if daily_vol is not None and daily_vol > 0:
            max_units = min(max_units, max(1, int(daily_vol * 0.5)))

        if max_units <= 0:
            continue

        allocated_cost = max_units * cost_per_unit
        allocated_profit = max_units * unit_profit

        remaining_budget -= allocated_cost
        total_invested += allocated_cost
        total_projected_net_profit += allocated_profit

        allocations.append({
            "item_id": cand.get("item_id"),
            "item_name": cand.get("item_name") or cand.get("item_id"),
            "buy_price": cand["buy_price"],
            "unit_cost_with_fee": cost_per_unit,
            "sell_price": cand["sell_price"],
            "quantity_integer": max_units,
            "total_silver_invested": allocated_cost,
            "projected_net_profit": allocated_profit,
            "unit_roi_pct": cand["roi_pct"],
        })

    portfolio_roi = round((total_projected_net_profit / total_invested * 100), 2) if total_invested > 0 else 0.0

    return {
        "budget_total": budget,
        "total_invested": total_invested,
        "cash_reserve_leftover": remaining_budget,
        "total_projected_net_profit": total_projected_net_profit,
        "blended_portfolio_roi_pct": portfolio_roi,
        "has_premium": has_premium,
        "total_items_allocated": len(allocations),
        "allocations": allocations
    }


def format_silver(amount: int | float) -> str:
    """Formata valor em prata com separadores de milhar no padrão pt-BR."""
    val = int(round(amount))
    return f"{val:,}".replace(",", ".") + " 🪙"


def format_silver_compact(amount: int | float) -> str:
    """Formata valor em prata no formato compacto (ex: 1.5M, 250k)."""
    val = float(amount)
    if abs(val) >= 1_000_000_000:
        return f"{val / 1_000_000_000:.2f}B 🪙"
    if abs(val) >= 1_000_000:
        return f"{val / 1_000_000:.2f}M 🪙"
    if abs(val) >= 1_000:
        return f"{val / 1_000:.1f}k 🪙"
    return f"{int(val)} 🪙"

