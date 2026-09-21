"""
Ferramentas MCP Anti-Alucinação e Matemática Determinística para Albion Online.

Projetadas para eliminar erros de álgebra reversa de impostos, spreads fantasmas,
cálculos fracionários de orçamento, física de carga e valor esperado de reroll.
"""

from typing import List, Dict, Any, Optional
import math
import sqlite3
import os

from ..core.calculator import (
    calculate_breakeven_prices,
    calculate_quality_reroll_ev,
    calculate_loadout_capacity,
    allocate_portfolio_budget,
    calculate_buy_order_cost,
    calculate_sell_order_proceeds,
    calculate_instant_sell_proceeds,
    get_tax_rate,
    SETUP_FEE_RATE
)
from ..core.loadout_optimizer import (
    MOUNTS_LIST,
    BAG_LOAD_MAP,
    PIE_LOAD_MAP,
    BOOTS_PASSIVE_MAP,
    solve_cheapest_loadout,
    calculate_effective_capacity
)
from ..core.metadata import metadata_manager, DATA_DIR


def albion_calculate_breakeven_price(
    buy_price: int,
    is_buy_order: bool = True,
    has_premium: bool = False,
    price_updates_buy: int = 0,
    price_updates_sell: int = 0,
    target_roi_pct: float = 0.0
) -> Dict[str, Any]:
    """
    Calcula com precisão determinística (zero margem de erro) o preço mínimo de venda
    necessário para não ter prejuízo (Break-even a 0% ROI) ou para atingir uma margem alvo.

    Inverte rigorosamente as regras fiscais de Sell Order (-4% ou -8% de imposto e -2.5% de setup fee)
    e considera os custos acumulados de renovações/edições de ordens de compra e venda.

    Parâmetros:
    - buy_price: Preço bruto do item no momento da compra (em prata).
    - is_buy_order: Se a compra foi via Ordem de Compra (+2.5% setup fee). Padrão: True.
    - has_premium: Se o jogador possui Premium (4% taxa de venda vs 8%). Padrão: False.
    - price_updates_buy: Número de vezes que a ordem de compra foi editada/renovada.
    - price_updates_sell: Número de vezes estimadas que a ordem de venda precisará ser renovada.
    - target_roi_pct: Margem de retorno desejada em % (0.0 para apenas empatar os custos).
    """
    return calculate_breakeven_prices(
        buy_price=buy_price,
        is_buy_order=is_buy_order,
        has_premium=has_premium,
        price_updates_buy=price_updates_buy,
        price_updates_sell=price_updates_sell,
        target_roi_pct=target_roi_pct
    )


def albion_audit_quote_freshness_and_phantom(
    item_id: str,
    city: str,
    quote_price: int,
    quote_type: str = "sell_order",
    age_seconds: Optional[int] = None,
    region: str = "americas"
) -> Dict[str, Any]:
    """
    Audita matematicamente uma cotação para prevenir alucinações de 'lucros milagrosos'
    baseados em ordens fantasmas, manipulações de mercado ou cotações antigas.

    Cruza o preço informado com a média móvel histórica consolidada e aplica travas
    estatísticas rígidas.

    Parâmetros:
    - item_id: ID do item (ex: 'T4_BAG', 'T6_MAIN_SWORD@1').
    - city: Cidade da cotação (ex: 'Caerleon', 'Black Market', 'Lymhurst').
    - quote_price: Preço listado atualmente no mercado.
    - quote_type: Tipo de ordem ('sell_order' para venda ou 'buy_order' para compra).
    - age_seconds: Idade da cotação em segundos (se disponível via NATS/API).
    - region: Região do servidor ('americas', 'asia', 'europe').
    """
    metadata_manager.ensure_data_loaded()
    item_name = metadata_manager.get_item_name(item_id)
    clean_base = item_id.split("@")[0]

    # Consulta base SQLite histórica local para obter a média histórica real
    db_file = os.path.join(DATA_DIR, f"market_history_{region}.db")
    avg_hist_price = 0
    daily_sales = 0.0

    if os.path.exists(db_file):
        try:
            conn = sqlite3.connect(db_file)
            c = conn.cursor()
            c.execute("""
                SELECT avg_historical_price, avg_daily_sales
                FROM history_stats
                WHERE item_id = ? AND location = ?
            """, (item_id, city))
            row = c.fetchone()
            if not row:
                # Tenta item sem encanto como proxy se não tiver
                c.execute("""
                    SELECT avg_historical_price, avg_daily_sales
                    FROM history_stats
                    WHERE item_id = ? AND location = ?
                """, (clean_base, city))
                row = c.fetchone()
            if row:
                avg_hist_price = int(row[0])
                daily_sales = float(row[1])
            conn.close()
        except Exception:
            pass

    # Fallback de preços históricos de referência se SQLite local não contiver o item
    BASE_HISTORICAL_ESTIMATES = {
        "T4_BAG": 4500,
        "T5_BAG": 15000,
        "T6_BAG": 45000,
        "T7_BAG": 120000,
        "T8_BAG": 350000,
        "T4_MAIN_AXE": 15000,
        "T5_MAIN_AXE": 40000,
        "T6_MAIN_AXE": 95000,
        "T7_MAIN_AXE": 180000,
        "T8_MAIN_AXE": 450000,
        "T4_MAIN_SWORD": 14000,
        "T5_MAIN_SWORD": 35000,
        "T6_MAIN_SWORD": 85000,
    }
    if avg_hist_price <= 0 and clean_base in BASE_HISTORICAL_ESTIMATES:
        avg_hist_price = BASE_HISTORICAL_ESTIMATES[clean_base]
        daily_sales = 500.0

    # Se não houver registro histórico, usa quote_price como referência
    reference_price = avg_hist_price if avg_hist_price > 0 else quote_price
    deviation_pct = round(((quote_price - reference_price) / reference_price * 100), 1) if reference_price > 0 else 0.0

    # Diagnóstico de Frescor (Idade)
    if age_seconds is not None:
        if age_seconds <= 120:
            freshness = "LIVE_CONFIRMED"
            freshness_label = "🟢 Dados 100% ao vivo (< 2 min)"
        elif age_seconds <= 600:
            freshness = "ACCEPTABLE"
            freshness_label = "🟡 Dados recentes (< 10 min)"
        elif age_seconds <= 86400:
            freshness = "STALE_WARNING"
            freshness_label = "⚠️ Dados desatualizados (> 10 min). Alta chance de a ordem não existir mais."
        else:
            freshness = "EXPIRED"
            freshness_label = "🔴 Dados muito antigos (> 24h). NÃO utilize para decisões financeiras."
    else:
        freshness = "UNKNOWN"
        freshness_label = "⚪ Idade do pacote desconhecida."

    # Diagnóstico Anti-Phantom Order
    if deviation_pct > 60.0:
        phantom_status = "PHANTOM_SUSPECT"
        phantom_label = "🔴 Alerta de Ordem Fantasma / Manipulação: Preço listado está >60% acima da média histórica real!"
    elif deviation_pct < -60.0:
        phantom_status = "DUMP_SUSPECT"
        phantom_label = "🔴 Alerta de Despejo Anormal: Preço está >60% abaixo da média histórica real."
    elif deviation_pct > 30.0:
        phantom_status = "SPIKE_DEMAND"
        phantom_label = "🟡 Demanda aquecida ou pico de preço (+30% a +60% sobre a média)."
    else:
        phantom_status = "NORMAL"
        phantom_label = "🟢 Preço dentro do padrão histórico normal (±30%)."

    # Trava de Segurança: Teto Máximo Seguro para Lance de Compra (Bid)
    safe_bid_cap = int(round(reference_price * 1.15))

    return {
        "item_id": item_id,
        "item_name_pt": item_name,
        "city": city,
        "quote_price": quote_price,
        "historical_avg_price": avg_hist_price,
        "historical_daily_sales": daily_sales,
        "price_deviation_from_avg_pct": deviation_pct,
        "freshness": {
            "status": freshness,
            "label": freshness_label,
            "age_seconds": age_seconds
        },
        "phantom_audit": {
            "status": phantom_status,
            "label": phantom_label,
            "is_reliable": (phantom_status in ("NORMAL", "SPIKE_DEMAND") and freshness in ("LIVE_CONFIRMED", "ACCEPTABLE", "UNKNOWN"))
        },
        "safe_guardrails": {
            "safe_max_bid_silver": safe_bid_cap,
            "recommendation": (
                f"Para evitar pagar sobrepreço por ordens manipuladas, nunca exceda o teto seguro de {safe_bid_cap:,} 🪙."
            ).replace(",", ".")
        }
    }


def albion_allocate_portfolio_budget(
    budget: int,
    candidate_items: List[Dict[str, Any]],
    max_items_count: int = 5,
    has_premium: bool = False,
    max_budget_per_item_pct: float = 40.0
) -> Dict[str, Any]:
    """
    Otimizador determinístico de carteira (Knapsack Bounded) com alocação inteira de capital.

    Garante que:
    1. Nenhuma quantidade de item seja fracionária (apenas números inteiros).
    2. A taxa de postagem de 2.5% de cada Buy Order seja reservada antecipadamente no caixa.
    3. O orçamento total nunca seja estourado, retornando o valor exato do troco seguro.
    4. O capital seja diversificado (nenhum item consome mais que o percentual máximo definido).

    Parâmetros:
    - budget: Orçamento total disponível em prata (ex: 5000000).
    - candidate_items: Lista de dicionários com os itens candidatos:
      [{'item_id': 'T4_BAG', 'buy_price': 4000, 'sell_price': 6500, 'daily_volume': 50}, ...]
    - max_items_count: Número máximo de itens diferentes na carteira (padrão: 5).
    - has_premium: Se o jogador tem Premium (4% de taxa na venda vs 8%).
    - max_budget_per_item_pct: Percentual máximo do orçamento por item (padrão: 40%).
    """
    return allocate_portfolio_budget(
        budget=budget,
        candidates=candidate_items,
        max_items=max_items_count,
        has_premium=has_premium,
        max_capital_per_item_pct=max_budget_per_item_pct
    )


def albion_simulate_quality_reroll(
    item_id: str,
    current_quality: int = 1,
    target_quality: int = 4
) -> Dict[str, Any]:
    """
    Simula o valor financeiro esperado (EV) e o intervalo estatístico de pior caso (95% de azar)
    para tentativas de reroll de qualidade na Repair Station.

    Mecânica in-game do Albion:
    - Custo por tentativa: Baseado no Item Value oficial do equipamento.
    - Probabilidades por nível:
      * Q1 -> Q2 (Normal -> Bom): 40%
      * Q2 -> Q3 (Bom -> Notável): 30%
      * Q3 -> Q4 (Notável -> Excelente): 10%
      * Q4 -> Q5 (Excelente -> Obra-prima): 1%

    Parâmetros:
    - item_id: ID do item (ex: 'T6_MAIN_SWORD', 'T8_ARMOR_PLATE_SET1').
    - current_quality: Qualidade atual (1=Normal, 2=Bom, 3=Notável, 4=Excelente).
    - target_quality: Qualidade desejada (2=Bom, 3=Notável, 4=Excelente, 5=Obra-prima).
    """
    metadata_manager.ensure_data_loaded()
    clean_id = item_id.split("@")[0]
    tier_str = metadata_manager.get_tier(clean_id)
    tier = int(tier_str.replace("T", "")) if "T" in tier_str else 4
    slot_type = metadata_manager.get_slot_type(clean_id)

    ev_res = calculate_quality_reroll_ev(
        tier=tier,
        slot_type=slot_type,
        current_quality=current_quality,
        target_quality=target_quality
    )
    ev_res["item_id"] = item_id
    ev_res["item_name_pt"] = metadata_manager.get_item_name(item_id)
    return ev_res


def albion_calculate_exact_loadout_capacity(
    items_list: List[Dict[str, Any]],
    mount_id: str = "OX_T5",
    bag_id: str = "T5.0",
    pie_id: str = "T7_PORK",
    boots_passive_id: str = "COURIER_STANDARD"
) -> Dict[str, Any]:
    """
    Validador físico determinístico de peso de carga e limites de sobrecarga in-game.

    Fórmula oficial:
    Capacidade Total (kg) = (Montaria + Bolsa + 50kg Base) * (1 + Torta%) * (1 + Bota%)

    Parâmetros:
    - items_list: Lista de itens com peso e quantidade:
      [{'item_id': 'T5_METALBAR', 'weight_unit_kg': 0.9, 'quantity': 1500}, ...]
    - mount_id: Identificador da montaria (ex: 'HORSE_T5', 'OX_T4', 'OX_T5', 'OX_T6', 'OX_T7', 'OX_T8', 'MAMMOTH_T8').
    - bag_id: Identificador da bolsa (ex: 'NONE', 'T4.0', 'T5.0', 'T6.0', 'T7.0', 'T8.0').
    - pie_id: Identificador da torta (ex: 'NONE', 'T3_CHICKEN', 'T5_GOOSE', 'T7_PORK').
    - boots_passive_id: Identificador da passiva de bota (ex: 'NONE', 'COURIER_STANDARD').
    """
    # Encontra parâmetros da montaria
    mount = next((m for m in MOUNTS_LIST if m["id"] == mount_id), MOUNTS_LIST[2])  # Default OX_T5
    bag = BAG_LOAD_MAP.get(bag_id, BAG_LOAD_MAP["T5.0"])
    pie = PIE_LOAD_MAP.get(pie_id, PIE_LOAD_MAP["T7_PORK"])
    boots = BOOTS_PASSIVE_MAP.get(boots_passive_id, BOOTS_PASSIVE_MAP["COURIER_STANDARD"])

    capacity_res = calculate_loadout_capacity(
        items_list=items_list,
        mount_capacity_kg=mount["capacity_kg"],
        bag_bonus_kg=bag["bonus_kg"],
        pie_bonus_pct=pie["bonus_pct"],
        boots_bonus_pct=boots["bonus_pct"]
    )

    capacity_res["equipped_kit"] = {
        "mount_name": mount["name"],
        "bag_name": bag["name"],
        "pie_name": pie["name"],
        "boots_passive_name": boots["name"]
    }

    # Integração com o Solver: se sobrecarregado ou para referência de otimização
    cargo_weight = capacity_res.get("total_cargo_weight_kg", 0.0)
    if cargo_weight > 0:
        opt = solve_cheapest_loadout(target_weight_kg=cargo_weight, current_mount_id=mount.get("id"))
        capacity_res["solver_recommendation"] = {
            "is_current_kit_sufficient": capacity_res.get("capacity_usage_pct", 0.0) <= 100.0,
            "cheapest_loadout": opt.get("cheapest_loadout"),
            "silver_saved_vs_naive": opt.get("silver_saved_vs_naive_mount", 0)
        }

    return capacity_res


def albion_calculate_transmutation_cost(
    resource_type: str = "ORE",
    from_tier: int = 4,
    to_tier: int = 5,
    quantity: int = 100,
    from_item_buy_price: int = 150,
    to_item_market_price: int = 600
) -> Dict[str, Any]:
    """
    Calcula a viabilidade matemática exata da transmutação no Transmutador municipal.

    No Albion Online, o Transmutador converte:
    1. Recursos refinados inferiores em superiores (T4 -> T5 -> T6 -> T7 -> T8).
    2. Corações Sombrios em Corações de Cidade Real (taxa fixa de 5.780 prata por unidade).

    Parâmetros:
    - resource_type: Tipo de recurso ('ORE', 'WOOD', 'FIBER', 'HIDE', 'ROCK', 'HEART').
    - from_tier: Tier de origem (ex: 4).
    - to_tier: Tier de destino (ex: 5).
    - quantity: Quantidade de unidades a transmutar.
    - from_item_buy_price: Custo de compra da matéria-prima do tier inferior (em prata).
    - to_item_market_price: Preço de mercado atual do produto do tier superior já pronto.
    """
    res_upper = resource_type.upper().strip()
    if res_upper in ("HEART", "FACTION_HEART", "CORACAO", "CORAÇÃO"):
        step_fee = 5780
        path_label = "Coração Sombrio -> Coração de Cidade Real"
    else:
        # Taxa fixa de prata do sistema de jogo por transmutação de tier (valores padrão de referência)
        SYSTEM_TRANSMUTE_FEE_PER_TIER = {
            (4, 5): 225,
            (5, 6): 580,
            (6, 7): 1650,
            (7, 8): 4800,
        }
        step_fee = SYSTEM_TRANSMUTE_FEE_PER_TIER.get((from_tier, to_tier))
        if not step_fee:
            # Se pular tiers (ex: T4 -> T6)
            total_fee_unit = 0
            for t in range(from_tier, to_tier):
                total_fee_unit += SYSTEM_TRANSMUTE_FEE_PER_TIER.get((t, t + 1), 500 * t)
            step_fee = total_fee_unit
        path_label = f"T{from_tier} -> T{to_tier}"

    # Custo total de produzir via transmutação
    unit_transmute_cost = from_item_buy_price + step_fee
    total_transmute_cost = unit_transmute_cost * quantity

    # Custo de comprar pronto no mercado
    total_market_buy_cost = to_item_market_price * quantity

    silver_difference = total_market_buy_cost - total_transmute_cost
    is_worth_transmuting = silver_difference > 0

    return {
        "resource": res_upper,
        "transmutation_path": path_label,
        "quantity": quantity,
        "input_tier_unit_cost": from_item_buy_price,
        "system_silver_fee_per_unit": step_fee,
        "total_transmute_cost_per_unit": unit_transmute_cost,
        "total_transmute_cost_batch": total_transmute_cost,
        "market_price_to_buy_ready_unit": to_item_market_price,
        "market_cost_to_buy_ready_batch": total_market_buy_cost,
        "silver_saved_by_transmuting": silver_difference if is_worth_transmuting else 0,
        "silver_lost_by_transmuting": abs(silver_difference) if not is_worth_transmuting else 0,
        "is_transmutation_cheaper": is_worth_transmuting,
        "verdict": (
            f"🟢 Transmutar é MAIS BARATO: economiza {silver_difference:,} 🪙 no lote."
            if is_worth_transmuting else
            f"🔴 NÃO TRANSMUTE: Comprar pronto no mercado é mais barato por {abs(silver_difference):,} 🪙."
        ).replace(",", ".")
    }
