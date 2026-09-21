"""
Ferramentas MCP para economia, impostos, encantamentos, refino e arbitragem.
"""

from typing import List, Dict, Any, Optional
from ..core.calculator import (
    calculate_trade_profit,
    calculate_buy_order_cost,
    calculate_sell_order_proceeds,
    calculate_instant_sell_proceeds,
    get_tax_rate,
    SETUP_FEE_RATE,
    ENCHANT_SLOT_COSTS
)
from ..core.metadata import metadata_manager
from ..core.polars_analytics import analytics_engine
from ..core.aodp_client import aodp_client


def albion_calculate_tax_and_fees(
    buy_price: int,
    sell_price: int,
    is_buy_order: bool = True,
    is_sell_order: bool = True,
    has_premium: bool = False,
    quantity: int = 1
) -> Dict[str, Any]:
    """
    Calcula os custos e lucros líquidos exatos de uma operação de mercado no Albion Online.

    Fórmulas oficiais (BUSINESS_RULES.md):
    - Setup Fee (2.5%): Cobrada ao criar ou editar ordens de compra/venda.
    - Transaction Tax: 4.0% (Com Premium) ou 8.0% (Sem Premium) sobre vendas.
    - Compra Direta (Instant Buy): Paga estritamente o valor listado (0% taxa).
    - Venda Direta (Instant Sell): Vende para Buy Order pagando apenas a Transaction Tax (0% Setup Fee).
    """
    return calculate_trade_profit(
        buy_price=buy_price,
        sell_price=sell_price,
        is_buy_order=is_buy_order,
        is_sell_order=is_sell_order,
        has_premium=has_premium,
        quantity=quantity
    )


def albion_simulate_enchantment(
    base_item_id: str,
    target_enchantment: int,
    base_item_buy_price: int,
    material_unit_price: int,
    target_item_sell_price: int,
    has_premium: bool = False,
    is_buy_order: bool = True,
    is_sell_order: bool = True
) -> Dict[str, Any]:
    """
    Simula o encantamento de um equipamento na Artifact Foundry (.0 -> .1, .2 ou .3).

    Regras Oficiais:
    - O encantamento consome Runas (.1), Almas (.2) ou Relíquias (.3) do mesmo tier do item.
    - Quantidades exatas por slot (múltiplos de 96):
      * Arma 2H: 384 materiais
      * Arma 1H: 288 materiais
      * Peitoral ou Bolsa: 192 materiais
      * Elmo, Botas, Secundários ou Capas: 96 materiais

    Parâmetros:
    - base_item_id: ID do item base (ex: 'T6_MAIN_SWORD', 'T4_BAG').
    - target_enchantment: Nível alvo de encantamento (1, 2 ou 3).
    - base_item_buy_price: Preço de compra do item base (em prata).
    - material_unit_price: Preço unitário do material de encantamento (Runa/Alma/Relíquia).
    - target_item_sell_price: Preço estimado de venda do item encantado no mercado.
    - has_premium: Se o jogador possui status Premium ativo (4% taxa de venda vs 8%).
    - is_buy_order: Se os insumos serão comprados via Ordem de Compra (+2.5% setup fee).
    - is_sell_order: Se o produto final será vendido via Ordem de Venda (-2.5% setup fee).
    """
    metadata_manager.ensure_data_loaded()
    clean_base = base_item_id.split("@")[0]
    tier = metadata_manager.get_tier(clean_base)
    slot_type = metadata_manager.get_slot_type(clean_base)
    materials_needed = metadata_manager.get_enchantment_cost(clean_base)

    target_item_id = f"{clean_base}@{target_enchantment}"
    material_name = {1: f"Runas {tier}", 2: f"Almas {tier}", 3: f"Relíquias {tier}"}.get(target_enchantment, "Materiais")

    # Custo de compra do item base
    base_cost = calculate_buy_order_cost(base_item_buy_price) if is_buy_order else base_item_buy_price

    # Custo dos materiais
    mat_cost_unit = calculate_buy_order_cost(material_unit_price) if is_buy_order else material_unit_price
    total_materials_cost = materials_needed * mat_cost_unit

    total_craft_cost = base_cost + total_materials_cost

    # Receita de venda
    net_revenue = (
        calculate_sell_order_proceeds(target_item_sell_price, has_premium=has_premium)
        if is_sell_order else
        calculate_instant_sell_proceeds(target_item_sell_price, has_premium=has_premium)
    )

    net_profit = net_revenue - total_craft_cost
    roi_pct = round((net_profit / total_craft_cost * 100), 2) if total_craft_cost > 0 else 0.0

    return {
        "base_item": {
            "item_id": clean_base,
            "name_pt": metadata_manager.get_item_name(clean_base),
            "slot_type": slot_type,
            "buy_price": base_item_buy_price,
            "effective_cost": base_cost
        },
        "enchantment": {
            "target_level": f".{target_enchantment}",
            "target_item_id": target_item_id,
            "target_name_pt": metadata_manager.get_item_name(target_item_id),
            "material_type": material_name,
            "materials_required": materials_needed,
            "material_unit_price": material_unit_price,
            "total_materials_cost": total_materials_cost
        },
        "financial_summary": {
            "total_investment": total_craft_cost,
            "gross_sell_price": target_item_sell_price,
            "net_revenue": net_revenue,
            "net_profit": net_profit,
            "roi_pct": roi_pct,
            "has_premium": has_premium,
            "verdict": "🟢 Lucrativo" if roi_pct >= 15.0 else ("🟡 Margem Baixa" if roi_pct > 0 else "🔴 Prejuízo")
        }
    }


def albion_calculate_refining(
    resource_type: str = "ORE",
    tier: int = 5,
    enchantment: int = 0,
    has_focus: bool = False,
    has_premium: bool = False,
    station_fee_per_100: int = 500
) -> Dict[str, Any]:
    """
    Calcula a viabilidade econômica do refino de um recurso específico em sua Capital Real especializada.

    Bônus Oficiais das Cidades Reais:
    - Thetford: Minério -> Barras (40% RRR base / 53.9% Foco)
    - Fort Sterling: Madeira -> Tábuas (40% RRR base / 53.9% Foco)
    - Lymhurst: Fibra -> Tecidos (40% RRR base / 53.9% Foco)
    - Martlock: Pelego -> Couro (40% RRR base / 53.9% Foco)
    - Bridgewatch: Pedra -> Blocos (40% RRR base / 53.9% Foco)

    Parâmetros:
    - resource_type: Tipo de recurso ('ORE', 'WOOD', 'FIBER', 'HIDE', 'ROCK').
    - tier: Tier do recurso (2 a 8).
    - enchantment: Nível de encantamento (0 a 4).
    - has_focus: Se o refino utilizará Foco de Artesanato (53.9% RRR vs 40.0%).
    - has_premium: Se o jogador possui Premium (4% taxa de venda vs 8%).
    - station_fee_per_100: Taxa da Estação de Artesanato por 100 de nutrição (padrão: 500).
    """
    return analytics_engine.calculate_refining(
        resource_type=resource_type,
        tier=tier,
        enchantment=enchantment,
        has_focus=has_focus,
        has_premium=has_premium,
        station_fee_per_100=station_fee_per_100
    )


def albion_calculate_cascade_refining(
    resource_type: str = "ORE",
    target_tier: int = 6,
    target_enchantment: int = 1,
    budget: int = 2000000,
    has_focus: bool = False,
    has_premium: bool = False,
    station_fee_per_100: int = 500
) -> Dict[str, Any]:
    """
    Simulação completa de Escalada de Matérias-Primas (Caminho B) com Ciclo Completo de Re-refino:
    - Compra de matérias-primas brutas até o orçamento informado.
    - Transporte até a capital especializada.
    - Re-refino em cascata de todas as sobras até o esgotamento dos insumos.
    - Otimização automática de montaria e peso de carga (Bolsas, Tortas de Porco).
    """
    return analytics_engine.calculate_cascade_refining(
        resource_type=resource_type,
        target_tier=target_tier,
        target_enchantment=target_enchantment,
        budget=budget,
        has_focus=has_focus,
        has_premium=has_premium,
        station_fee_per_100=station_fee_per_100
    )


async def albion_find_arbitrage_opportunities(
    item_ids: List[str],
    source_cities: Optional[List[str]] = None,
    target_cities: Optional[List[str]] = None,
    min_roi_pct: float = 12.0,
    has_premium: bool = False,
    region: str = "americas"
) -> Dict[str, Any]:
    """
    Identifica oportunidades de arbitragem e transporte de itens entre cidades reais ou para o Black Market.

    Compara o menor preço de venda na cidade de origem com a melhor ordem de compra ou venda na cidade de destino,
    descontando todas as taxas fiscais (4% premium / 8% sem premium e setup fees).

    Parâmetros:
    - item_ids: Lista de itens a analisar.
    - source_cities: Cidades de compra (padrão: 5 capitais reais seguras).
    - target_cities: Cidades de destino (padrão: Caerleon, Black Market e Capitais Reais).
    - min_roi_pct: Retorno mínimo sobre investimento (padrão: 12.0%).
    - has_premium: Status de Premium ativo.
    """
    if not item_ids:
        return {"error": "item_ids não pode estar vazio.", "opportunities": []}

    prices = await aodp_client.get_current_prices(item_ids=item_ids, region=region)
    if not prices:
        return {"opportunities": [], "message": "Nenhuma cotação encontrada no AODP."}

    # Indexar por (item_id, quality, city)
    by_item_city = {}
    for p in prices:
        key = (p.get("item_id"), p.get("quality", 1), p.get("city"))
        by_item_city[key] = p

    sources = set(source_cities or ["Bridgewatch", "Lymhurst", "Fort Sterling", "Martlock", "Thetford"])
    targets = set(target_cities or ["Caerleon", "Black Market", "Bridgewatch", "Lymhurst", "Fort Sterling", "Martlock", "Thetford"])

    opportunities = []

    for it in set(item_ids):
        for q in [1, 2, 3]:
            # Procura menor preço de compra em source
            best_buy = None
            for s_city in sources:
                quote = by_item_city.get((it, q, s_city))
                if not quote:
                    continue
                sell_min = quote.get("sell_price_min", 0)
                if sell_min > 0 and (best_buy is None or sell_min < best_buy["price"]):
                    best_buy = {"city": s_city, "price": sell_min}

            if not best_buy:
                continue

            # Procura melhor destino de venda
            for t_city in targets:
                if t_city == best_buy["city"]:
                    continue
                target_quote = by_item_city.get((it, q, t_city))
                if not target_quote:
                    continue

                if t_city == "Black Market":
                    target_price = target_quote.get("buy_price_max", 0)
                    is_sell_order = False  # Venda direta para buy order do sistema
                else:
                    target_price = target_quote.get("sell_price_min", 0)
                    is_sell_order = True

                if target_price <= 0:
                    continue

                trade = calculate_trade_profit(
                    buy_price=best_buy["price"],
                    sell_price=target_price,
                    is_buy_order=False,  # Instant buy na origem
                    is_sell_order=is_sell_order,
                    has_premium=has_premium
                )

                if trade["roi_pct"] >= min_roi_pct:
                    opportunities.append({
                        "item_id": it,
                        "item_name_pt": metadata_manager.get_item_name(it),
                        "quality": q,
                        "buy_city": best_buy["city"],
                        "buy_price": best_buy["price"],
                        "sell_city": t_city,
                        "sell_price": target_price,
                        "is_black_market": (t_city == "Black Market"),
                        "unit_profit": trade["unit_profit"],
                        "roi_pct": trade["roi_pct"],
                        "is_safe_route": (best_buy["city"] in sources and t_city in sources),
                    })

    opportunities.sort(key=lambda x: x["unit_profit"], reverse=True)

    return {
        "total_opportunities": len(opportunities),
        "min_roi_filter": min_roi_pct,
        "has_premium": has_premium,
        "opportunities": opportunities[:30]
    }
