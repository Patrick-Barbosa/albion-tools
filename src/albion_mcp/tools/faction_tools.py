"""
Ferramentas MCP para Inteligência de Transporte de Facção e Economia de Corações.
"""

from typing import Dict, Any, Optional, List
from ..core.faction_transport import (
    calculate_faction_transport_plan,
    simulate_post_trip_decision_tree,
    HEARTS_METADATA,
    FACTION_PACK_SPECS,
    TRANSMUTE_FEE_SILVER
)
from ..core.cape_crafting import (
    evaluate_cape_vs_raw_heart_profit,
    calculate_cape_crafting_cost
)
try:
    from ..core.aodp_client import aodp_client
except ImportError:
    aodp_client = None


async def albion_calculate_faction_transport(
    current_city: str,
    available_silver: int,
    risk_profile: str = "ALLOW_RED_ZONE",
    has_premium: bool = True,
    mount_type: str = "T5_BOAR",
    session_mode: str = "CONTINUOUS_LOOP",
    pack_size: int = 7,
    target_destination: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calcula e planeja missões de transporte de corações de facção (Faction Smuggling).

    Implementa o contrato Round-Trip oficial (ida ao contrabandista e retorno à cidade de origem),
    pesagem física dos fardos (125 kg, 668 kg, 1623 kg), dimensionamento de montarias no Motor 1
    e árvore de decisão determinística (Transmutação vs Recompra de Mercado).

    GUARDRAILS OBRIGATÓRIOS:
    - current_city: Cidade onde o jogador está sediado ('Lymhurst', 'Bridgewatch', 'Fort Sterling', 'Thetford', 'Martlock').
    - available_silver: Saldo de prata na carteira para orçar fardo ou transmutação.
    - risk_profile: 'SAFE_ONLY' (apenas Zonas Azuis/Amarelas) ou 'ALLOW_RED_ZONE' (permite Caerleon / Full Loot).
    - has_premium: True (4% imposto) ou False (8% imposto).
    - mount_type: Montaria utilizada (padrão: 'T5_BOAR' ou bois 'T4_OX'..'T8_OX').
    - session_mode: 'CONTINUOUS_LOOP' (giro rápido sem parar) ou 'PATIENT_TRADER' (ordens de venda / capas).
    - pack_size: Quantidade de corações do fardo (3 = Leve/125kg, 7 = Médio/668kg, 15 = Pesado/1623kg).
    - target_destination: Cidade de destino opcional caso o jogador queira forçar uma rota específica.
    """
    # Consulta cotações em tempo real de todos os corações de facção via AODP
    all_heart_ids = [h["item_id"] for h in HEARTS_METADATA.values()]
    live_prices = {}

    if aodp_client is not None:
        try:
            raw_prices = await aodp_client.get_current_prices(item_ids=all_heart_ids)
            for p in raw_prices:
                it_id = p.get("item_id")
                sell_min = p.get("sell_price_min", 0)
                buy_max = p.get("buy_price_max", 0)
                # Prioriza sell_price_min se válido, caso contrário buy_max
                valid_price = sell_min if sell_min > 0 else buy_max
                if it_id and valid_price > 0:
                    if it_id not in live_prices or valid_price < live_prices[it_id]:
                        live_prices[it_id] = valid_price
        except Exception:
            # Em caso de falha de conexão ou rate limit, o motor usa preços de referência históricos
            live_prices = None

    return calculate_faction_transport_plan(
        current_city=current_city,
        available_silver=available_silver,
        risk_profile=risk_profile,
        has_premium=has_premium,
        mount_type=mount_type,
        session_mode=session_mode,
        pack_size=pack_size,
        target_destination=target_destination,
        mock_heart_prices=live_prices if live_prices else None
    )


def albion_simulate_heart_cycle(
    origin_city: str = "Lymhurst",
    destination_city: str = "Caerleon",
    pack_size: int = 7,
    num_cycles: int = 6,
    origin_heart_price: int = 45000,
    shadowheart_price: int = 62000,
    has_premium: bool = True
) -> Dict[str, Any]:
    """
    Simula a execução contínua de múltiplos ciclos de transporte (ex: 1 hora = 6 viagens de Javali T5).

    Compara os 3 caminhos de reciclagem de capital:
    1. Injeção Externa de Prata (recompra contínua de mercado e estocagem de sombrios).
    2. Expansão Perpétua por Transmutação Total (11 sombrios -> 11 arbóreos a 5.780 prata).
    3. Loop Híbrido Autossustentável (transmuta 7 para rodar de novo e vende os 4 restantes via Instant Sell).

    Parâmetros:
    - origin_city: Cidade de partida (ex: 'Lymhurst').
    - destination_city: Destino da rota (ex: 'Caerleon').
    - pack_size: Tamanho do fardo (3, 7 ou 15).
    - num_cycles: Quantidade de viagens completas simuladas (padrão: 6 = ~1 hora).
    - origin_heart_price: Cotação de mercado do coração de origem.
    - shadowheart_price: Cotação de mercado do coração sombrio.
    - has_premium: Status Premium (4% vs 8%).
    """
    tax_rate = 0.04 if has_premium else 0.08
    is_caerleon = (destination_city.lower() == "caerleon")

    # Recompensa por viagem (ex: 7 -> 11 em Caerleon)
    from ..core.faction_transport import calculate_faction_route_reward
    hearts_out = calculate_faction_route_reward(origin_city, destination_city, pack_size)
    hearts_delta = hearts_out - pack_size

    # Tempo total estimado (10 min por ciclo de Javali T5)
    total_minutes = num_cycles * 10.0

    # 1. Caminho 1: Injeção de Prata Externa
    capital_needed_c1 = num_cycles * pack_size * origin_heart_price
    total_shadowhearts_accum_c1 = num_cycles * hearts_out
    gross_revenue_c1 = total_shadowhearts_accum_c1 * shadowheart_price
    net_revenue_c1 = int(gross_revenue_c1 * (1.0 - tax_rate))
    net_profit_c1 = net_revenue_c1 - capital_needed_c1

    # 2. Caminho 2: Expansão Perpétua Total (Transmuta todos hearts_out a 5.780)
    # Custo de entrada inicial: compra de apenas 1 fardo de pack_size
    initial_seed_cost_c2 = pack_size * origin_heart_price
    transmute_cost_per_cycle_c2 = hearts_out * TRANSMUTE_FEE_SILVER if is_caerleon else 0
    total_transmute_cost_c2 = num_cycles * transmute_cost_per_cycle_c2
    surplus_origin_hearts_stored_c2 = num_cycles * hearts_delta if is_caerleon else 0
    surplus_valuation_c2 = surplus_origin_hearts_stored_c2 * origin_heart_price

    # 3. Caminho 3: Loop Híbrido Autossustentável (Transmuta pack_size e vende hearts_delta imediatamente)
    initial_seed_cost_c3 = pack_size * origin_heart_price
    transmute_required_per_cycle_c3 = pack_size * TRANSMUTE_FEE_SILVER if is_caerleon else 0
    total_transmute_cost_c3 = num_cycles * transmute_required_per_cycle_c3
    total_surplus_sold_c3 = num_cycles * hearts_delta
    gross_surplus_revenue_c3 = total_surplus_sold_c3 * shadowheart_price
    net_surplus_revenue_c3 = int(gross_surplus_revenue_c3 * (1.0 - tax_rate))
    liquid_cash_in_pocket_c3 = net_surplus_revenue_c3 - total_transmute_cost_c3

    return {
        "simulation_parameters": {
            "origin_city": origin_city,
            "destination_city": destination_city,
            "pack_size": pack_size,
            "hearts_returned_per_trip": hearts_out,
            "hearts_profit_per_trip": hearts_delta,
            "num_cycles": num_cycles,
            "total_playtime_minutes": total_minutes,
            "has_premium": has_premium
        },
        "path_1_external_reinvestment": {
            "strategy": "Comprar fardo no mercado a cada ciclo e guardar todos os corações recebidos",
            "capital_required_silver": capital_needed_c1,
            "total_hearts_accumulated": total_shadowhearts_accum_c1,
            "net_revenue_if_sold_silver": net_revenue_c1,
            "net_profit_silver": net_profit_c1,
            "silver_per_hour": int((net_profit_c1 / total_minutes) * 60)
        },
        "path_2_perpetual_expansion": {
            "strategy": "Transmutar todos os corações recebidos em corações arbóreos para expandir o estoque",
            "initial_seed_capital": initial_seed_cost_c2,
            "total_transmute_fees_paid": total_transmute_cost_c2,
            "surplus_origin_hearts_in_chest": surplus_origin_hearts_stored_c2,
            "surplus_equity_valuation_silver": surplus_valuation_c2,
            "net_equity_gain_silver": surplus_valuation_c2 - total_transmute_cost_c2
        },
        "path_3_hybrid_autoloop": {
            "strategy": "Transmutar apenas o necessário para a próxima viagem e vender o lucro líquido imediatamente",
            "initial_seed_capital": initial_seed_cost_c3,
            "total_transmute_fees_paid": total_transmute_cost_c3,
            "surplus_hearts_sold_for_cash": total_surplus_sold_c3,
            "liquid_cash_profit_in_pocket": liquid_cash_in_pocket_c3,
            "silver_per_hour": int((liquid_cash_in_pocket_c3 / total_minutes) * 60)
        }
    }


def albion_evaluate_heart_downstream(
    city_faction: str = "Lymhurst",
    tier: int = 4,
    enchantment: int = 2,
    target_quality: int = 1,
    heart_market_price: int = 45000,
    cape_market_sell_price: int = 160000,
    has_premium: bool = True
) -> Dict[str, Any]:
    """
    Avalia a esteira downstream de manufatura de Capas de Facção (T4..T8).

    Compara se é mais lucrativo vender os corações brutos ou utilizá-los para
    confeccionar Capas de Facção encantadas (.1/.2/.3) com reroll de qualidade.

    Parâmetros:
    - city_faction: Cidade da capa ('Lymhurst', 'Fort Sterling', 'Caerleon', etc.).
    - tier: Tier da capa (4 a 8).
    - enchantment: Encantamento (0 a 3, consumindo 96 insumos por nível).
    - target_quality: 1 (Normal), 2 (Bom), 3 (Notável), 4 (Excelente), 5 (Obra-prima).
    - heart_market_price: Cotação de mercado do coração de facção.
    - cape_market_sell_price: Preço de venda listado da capa acabada no mercado.
    - has_premium: Status Premium (4% vs 8%).
    """
    return evaluate_cape_vs_raw_heart_profit(
        city_faction=city_faction,
        tier=tier,
        enchantment=enchantment,
        target_quality=target_quality,
        heart_market_price=heart_market_price,
        cape_market_sell_price=cape_market_sell_price,
        has_premium=has_premium
    )
