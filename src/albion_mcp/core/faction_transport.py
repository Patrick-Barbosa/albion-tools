"""
Motor de Transporte de Facção e Economia de Corações (Faction Transport Engine) para Albion Online.

Implementa o ciclo oficial Round-Trip (entrega final na cidade de origem), a física
determinística de pesagem de fardos (125 kg, 668 kg, 1623 kg), topologia do Continente Real,
benchmark de tempo calibrado (Javali T5) e a árvore de decisão matemática dos 11 corações
(Recompra de Mercado vs Loops Perpétuos de Transmutação a 5.780 prata).
"""

from typing import Dict, Any, List, Optional, Tuple
try:
    from .loadout_optimizer import solve_cheapest_loadout
except ImportError:
    from loadout_optimizer import solve_cheapest_loadout

# Identificadores oficiais dos corações de recurso no Albion Online
HEARTS_METADATA = {
    "Lymhurst": {
        "item_id": "T4_HEART_WOOD",
        "name_pt": "Coração da Árvore (Arbóreo)",
        "name_en": "Treeheart",
        "resource": "Madeira / Floresta"
    },
    "Fort Sterling": {
        "item_id": "T4_HEART_MOUNTAIN",
        "name_pt": "Coração da Montanha",
        "name_en": "Mountainheart",
        "resource": "Minério de Neve / Montanha"
    },
    "Bridgewatch": {
        "item_id": "T4_HEART_BEAST",
        "name_pt": "Coração da Fera",
        "name_en": "Beastheart",
        "resource": "Peles / Estepes"
    },
    "Thetford": {
        "item_id": "T4_HEART_SWAMP",
        "name_pt": "Coração do Pântano",
        "name_en": "Vineheart",
        "resource": "Fibras / Pântano"
    },
    "Martlock": {
        "item_id": "T4_HEART_ROCK",
        "name_pt": "Coração da Rocha",
        "name_en": "Rockheart",
        "resource": "Pedras / Planalto"
    },
    "Caerleon": {
        "item_id": "T4_HEART_UNDEAD",
        "name_pt": "Coração Sombrio",
        "name_en": "Shadowheart",
        "resource": "Mercado Negro / Sombrio"
    }
}

# Pesagem exata dos fardos derivada das medições empíricas in-game (Base: 50 kg)
FACTION_PACK_SPECS = {
    3: {
        "size_label": "LIGHT",
        "hearts_in": 3,
        "load_pct_naked": 250.0,
        "weight_kg": 125.0,
        "description": "Fardo Leve (125 kg). Suportado por montarias leves com bolsa."
    },
    7: {
        "size_label": "MEDIUM",
        "hearts_in": 7,
        "load_pct_naked": 1336.0,
        "weight_kg": 668.0,
        "description": "Fardo Médio (668 kg). Suportado com perfeição pelo Javali T5 e Boi T4/T5."
    },
    15: {
        "size_label": "HEAVY",
        "hearts_in": 15,
        "load_pct_naked": 3246.0,
        "weight_kg": 1623.0,
        "description": "Fardo Pesado (1623 kg). Exige Boi T6+ ou Urso Cinzento T8 para não sobrecarregar."
    }
}

# Taxa fixa municipal do sistema para transmutar 1 Coração Sombrio em 1 Coração de Cidade Real
TRANSMUTE_FEE_SILVER = 5780

# Topologia do Continente Real: Vizinhas (D=1), Intermediária (D=2), Extrema Oposta (D=2+) e Caerleon (Centro)
TOPOLOGY_MAP = {
    "Lymhurst": {
        "neighbors": ["Fort Sterling", "Bridgewatch"],
        "intermediate": "Thetford",
        "extreme": "Martlock",
        "caerleon": "Caerleon"
    },
    "Fort Sterling": {
        "neighbors": ["Thetford", "Lymhurst"],
        "intermediate": "Bridgewatch",
        "extreme": "Martlock",
        "caerleon": "Caerleon"
    },
    "Thetford": {
        "neighbors": ["Martlock", "Fort Sterling"],
        "intermediate": "Lymhurst",
        "extreme": "Bridgewatch",
        "caerleon": "Caerleon"
    },
    "Martlock": {
        "neighbors": ["Thetford", "Bridgewatch"],
        "intermediate": "Fort Sterling",
        "extreme": "Lymhurst",
        "caerleon": "Caerleon"
    },
    "Bridgewatch": {
        "neighbors": ["Martlock", "Lymhurst"],
        "intermediate": "Thetford",
        "extreme": "Fort Sterling",
        "caerleon": "Caerleon"
    }
}

# Tabela de Retorno de Corações por Categoria de Distância
REWARDS_BY_DISTANCE_CATEGORY = {
    "NEIGHBOR": {3: 4, 7: 9, 15: 18},
    "INTERMEDIATE": {3: 5, 7: 11, 15: 21},
    "EXTREME": {3: 5, 7: 12, 15: 22},
    "CAERLEON": {3: 6, 7: 11, 15: 21}
}

# Tempos médios de viagem Round-Trip (Ida e Volta) calibrados para montaria padrão (Javali T5)
ROUND_TRIP_MINUTES_BENCHMARK = {
    "CAERLEON": 10.0,
    "NEIGHBOR": 10.5,
    "INTERMEDIATE": 16.0,
    "EXTREME": 20.0
}


def get_route_category(origin_city: str, destination_city: str) -> Tuple[str, str]:
    """
    Retorna (categoria_distancia, nivel_risco) para uma rota.
    Categorias: 'NEIGHBOR', 'INTERMEDIATE', 'EXTREME', 'CAERLEON'.
    Risco: 'SAFE_ZONES' (Azul/Amarela) ou 'RED_ZONE_FULL_LOOT'.
    """
    if destination_city.lower() == "caerleon":
        return "CAERLEON", "RED_ZONE_FULL_LOOT"

    topo = TOPOLOGY_MAP.get(origin_city)
    if not topo:
        raise ValueError(f"Cidade de origem inválida: {origin_city}")

    if destination_city in topo["neighbors"]:
        return "NEIGHBOR", "SAFE_ZONES"
    elif destination_city == topo["intermediate"]:
        return "INTERMEDIATE", "SAFE_ZONES"
    elif destination_city == topo["extreme"]:
        return "EXTREME", "SAFE_ZONES"
    else:
        # Fallback conservador
        return "EXTREME", "SAFE_ZONES"


def calculate_faction_route_reward(origin_city: str, destination_city: str, pack_size: int) -> int:
    """Calcula a quantidade bruta de corações recebidos na entrega final."""
    if pack_size not in (3, 7, 15):
        raise ValueError(f"Tamanho de fardo inválido: {pack_size}. Use 3, 7 ou 15.")

    cat, _ = get_route_category(origin_city, destination_city)
    rewards_table = REWARDS_BY_DISTANCE_CATEGORY[cat]
    return rewards_table[pack_size]


def evaluate_transmute_arbitrage(
    origin_heart_ask_price: int,
    shadowheart_bid_price: int,
    has_premium: bool = True
) -> Dict[str, Any]:
    """
    Equação de Decisão Determinística:
    Compara o custo de obter 1 coração de origem via Transmutação (5.780 prata)
    vs Vender o Sombrio no mercado e comprar o de origem com a prata obtida.
    """
    tax_rate = 0.04 if has_premium else 0.08
    shadowheart_net_sell = int(shadowheart_bid_price * (1.0 - tax_rate))

    # Custo de 1 coração de origem via transmutação:
    # O jogador abre mão de vender o sombrio (perde shadowheart_net_sell) e paga 5.780 prata de taxa
    effective_transmute_cost = shadowheart_net_sell + TRANSMUTE_FEE_SILVER

    # Custo de comprar 1 coração de origem direto no mercado
    market_buy_cost = origin_heart_ask_price

    delta_silver = market_buy_cost - effective_transmute_cost

    if delta_silver > 0:
        recommendation = "TRANSMUTE"
        action_label = "👉 RECOMENDAÇÃO: TRANSMUTAR (Loop Perpétuo)"
        reason = (
            f"O coração de origem está caro no mercado ({market_buy_cost:,} ⚗). "
            f"Transmutar o sombrio pagando 5.780 ⚗ de taxa economiza {delta_silver:,} ⚗ por coração."
        )
    else:
        recommendation = "SELL_AND_BUY_MARKET"
        action_label = "👉 RECOMENDAÇÃO: VENDER SOMBRIO E RECOMPRAR NO MERCADO"
        reason = (
            f"O coração sombrio está altamente valorizado ({shadowheart_bid_price:,} ⚗). "
            f"Vender o sombrio e comprar o de origem gera uma sobra líquida de {abs(delta_silver):,} ⚗ por coração."
        )

    return {
        "recommendation": recommendation,
        "action_label": action_label,
        "delta_silver_per_heart": delta_silver,
        "effective_transmute_cost": effective_transmute_cost,
        "market_buy_cost": market_buy_cost,
        "transmute_system_fee": TRANSMUTE_FEE_SILVER,
        "shadowheart_net_sell": shadowheart_net_sell,
        "reason": reason
    }


def simulate_post_trip_decision_tree(
    origin_city: str,
    destination_city: str,
    pack_size: int,
    origin_heart_price: int,
    destination_heart_price: int,
    available_silver: int,
    has_premium: bool = True,
    session_mode: str = "CONTINUOUS_LOOP"
) -> Dict[str, Any]:
    """
    Simula e compara os 4 ramos estratégicos pós-viagem para os corações obtidos:
    1. Injeção de Prata Externa (Acumulação no baú)
    2. Expansão Perpétua por Transmutação Total (se Caerleon)
    3. Loop Híbrido Autossustentável (se Caerleon)
    4. Venda Direta / Manufatura de Capas
    """
    hearts_in = pack_size
    hearts_out = calculate_faction_route_reward(origin_city, destination_city, pack_size)
    tax_rate = 0.04 if has_premium else 0.08

    is_caerleon = (destination_city.lower() == "caerleon")

    # Ramo 1: Injeção de Prata Externa
    # Guarda os corações ganhos e compra novos hearts_in com saldo bancário
    cost_rebuy = hearts_in * origin_heart_price
    can_afford_rebuy = (available_silver >= cost_rebuy)

    # Ramo 2: Expansão Perpétua (Transmutar todos hearts_out em corações de origem)
    transmute_all_cost = hearts_out * TRANSMUTE_FEE_SILVER if is_caerleon else 0
    surplus_hearts_branch2 = (hearts_out - hearts_in) if is_caerleon else 0

    # Ramo 3: Loop Híbrido (Transmutar apenas hearts_in para reiniciar viagem, vender excedente)
    transmute_required_cost = hearts_in * TRANSMUTE_FEE_SILVER if is_caerleon else 0
    surplus_hearts_branch3 = (hearts_out - hearts_in) if is_caerleon else 0
    surplus_net_silver_branch3 = int(surplus_hearts_branch3 * destination_heart_price * (1.0 - tax_rate)) if is_caerleon else 0
    net_profit_branch3 = surplus_net_silver_branch3 - transmute_required_cost if is_caerleon else 0

    # Arbitragem ao vivo se Caerleon
    arbitrage_eval = None
    if is_caerleon:
        arbitrage_eval = evaluate_transmute_arbitrage(
            origin_heart_ask_price=origin_heart_price,
            shadowheart_bid_price=destination_heart_price,
            has_premium=has_premium
        )

    # Ramo 4: Venda Direta Pura de Todos os Corações Recebidos
    gross_revenue = hearts_out * destination_heart_price
    net_revenue = int(gross_revenue * (1.0 - tax_rate))
    direct_profit = net_revenue - (hearts_in * origin_heart_price)

    # Recomendação de acordo com o modo de sessão
    if session_mode == "CONTINUOUS_LOOP":
        if is_caerleon:
            recommended_branch = "BRANCH_3_HYBRID_LOOP"
            strategy_summary = (
                "Sessão Contínua (Giro Rápido): Transmute os 7 corações sombrios pagando 40.460 ⚗ "
                "para reiniciar a viagem imediatamente e venda os 4 sombrios restantes para colher lucro vivo."
            )
        else:
            recommended_branch = "BRANCH_1_REBUY"
            strategy_summary = (
                f"Sessão Contínua: Venda os corações de {destination_city} no mercado local "
                f"ou use a prata para recomprar fardos de {origin_city} e rodar de novo."
            )
    else:  # PATIENT_TRADER
        recommended_branch = "BRANCH_4_PATIENT_SALE_OR_CAPES"
        strategy_summary = (
            "Sessão Paciente / Artesão: Confeccione Capas de Facção com os corações ou posicione "
            "ordens de venda (Sell Orders) com paciência para colher o preço de pico histórico."
        )

    return {
        "hearts_in": hearts_in,
        "hearts_out": hearts_out,
        "net_hearts_delta": hearts_out - hearts_in,
        "is_caerleon": is_caerleon,
        "arbitrage_evaluation": arbitrage_eval,
        "recommended_branch": recommended_branch,
        "strategy_summary": strategy_summary,
        "branches": {
            "branch_1_external_rebuy": {
                "description": "Comprar novo fardo com prata do banco e estocar corações no baú",
                "cost_silver": cost_rebuy,
                "can_afford": can_afford_rebuy
            },
            "branch_2_perpetual_expansion": {
                "description": "Transmutar todos os corações sombrios em corações arbóreos para crescer a fábrica",
                "transmute_cost_silver": transmute_all_cost,
                "surplus_origin_hearts_stored": surplus_hearts_branch2,
                "applicable": is_caerleon
            },
            "branch_3_hybrid_loop": {
                "description": "Transmutar os necessários para reiniciar e vender o excedente",
                "transmute_cost_silver": transmute_required_cost,
                "surplus_hearts_sold": surplus_hearts_branch3,
                "immediate_net_silver_profit": net_profit_branch3,
                "applicable": is_caerleon
            },
            "branch_4_direct_sale": {
                "description": "Liquidar todos os corações recebidos no mercado",
                "net_revenue_silver": net_revenue,
                "net_profit_silver": direct_profit
            }
        }
    }


def validate_faction_inputs(
    current_city: str,
    available_silver: int,
    risk_profile: str,
    has_premium: bool,
    mount_type: str,
    session_mode: str
) -> Dict[str, Any]:
    """
    Guardrail de Validação Prévia:
    Verifica a conformidade rigorosa dos 6 parâmetros obrigatórios antes de qualquer cálculo.
    """
    errors = []

    valid_cities = list(TOPOLOGY_MAP.keys())
    normalized_city = None
    for c in valid_cities:
        if c.lower() == current_city.strip().lower():
            normalized_city = c
            break

    if not normalized_city:
        errors.append(
            f"Cidade 'current_city' inválida: '{current_city}'. "
            f"Deve ser uma das 5 capitais reais: {valid_cities}."
        )

    if available_silver is None or available_silver < 0:
        errors.append("Saldo de prata 'available_silver' deve ser um valor inteiro não-negativo.")

    valid_risks = ("SAFE_ONLY", "ALLOW_RED_ZONE")
    norm_risk = risk_profile.strip().upper() if risk_profile else ""
    if norm_risk not in valid_risks:
        errors.append(f"Perfil de risco 'risk_profile' inválido: '{risk_profile}'. Use {valid_risks}.")

    valid_modes = ("CONTINUOUS_LOOP", "PATIENT_TRADER")
    norm_mode = session_mode.strip().upper() if session_mode else ""
    if norm_mode not in valid_modes:
        errors.append(f"Modo de sessão 'session_mode' inválido: '{session_mode}'. Use {valid_modes}.")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "normalized_city": normalized_city,
        "normalized_risk": norm_risk,
        "normalized_mode": norm_mode,
        "has_premium": bool(has_premium),
        "available_silver": int(available_silver) if available_silver is not None else 0,
        "mount_type": mount_type
    }


def calculate_faction_transport_plan(
    current_city: str,
    available_silver: int,
    risk_profile: str = "ALLOW_RED_ZONE",
    has_premium: bool = True,
    mount_type: str = "T5_BOAR",
    session_mode: str = "CONTINUOUS_LOOP",
    pack_size: int = 7,
    target_destination: Optional[str] = None,
    mock_heart_prices: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """
    Função Master de Execução do Motor 2:
    Valida guardrails, resolve compatibilidade física no Motor 1 e projeta lucros da rota.
    """
    # 1. Validação de Guardrails
    guard = validate_faction_inputs(
        current_city=current_city,
        available_silver=available_silver,
        risk_profile=risk_profile,
        has_premium=has_premium,
        mount_type=mount_type,
        session_mode=session_mode
    )
    if not guard["is_valid"]:
        return {
            "status": "GUARDRAIL_VALIDATION_FAILED",
            "message": "Faltam parâmetros obrigatórios ou foram passados com formato inválido.",
            "errors": guard["errors"]
        }

    origin = guard["normalized_city"]
    pack_spec = FACTION_PACK_SPECS.get(pack_size)
    if not pack_spec:
        return {
            "status": "INVALID_PACK_SIZE",
            "message": f"Tamanho de fardo inválido: {pack_size}. Escolha 3, 7 ou 15 corações."
        }

    target_weight_kg = pack_spec["weight_kg"]

    # 2. Consulta ao Motor 1 (Loadout Solver) para validar a montaria do jogador
    loadout_advice = solve_cheapest_loadout(
        target_weight_kg=target_weight_kg,
        current_mount_id=mount_type,
        risk_level=guard["normalized_risk"]
    )

    # 3. Determinação dos destinos elegíveis
    topo = TOPOLOGY_MAP[origin]
    eligible_destinations = []
    if guard["normalized_risk"] == "ALLOW_RED_ZONE":
        eligible_destinations.append(topo["caerleon"])

    eligible_destinations.extend(topo["neighbors"])
    eligible_destinations.append(topo["intermediate"])
    eligible_destinations.append(topo["extreme"])

    if target_destination:
        norm_dest = target_destination.strip().title()
        if norm_dest not in eligible_destinations:
            return {
                "status": "DESTINATION_BLOCKED_BY_RISK_OR_INVALID",
                "message": f"Destino '{target_destination}' não é elegível para a política de risco '{guard['normalized_risk']}' ou cidade de origem '{origin}'.",
                "eligible_destinations": eligible_destinations
            }
        eligible_destinations = [norm_dest]

    # Preços padrão de referência (fallback para testes offline)
    default_prices = {
        "T4_HEART_WOOD": 45000,
        "T4_HEART_MOUNTAIN": 46000,
        "T4_HEART_BEAST": 44000,
        "T4_HEART_SWAMP": 47000,
        "T4_HEART_ROCK": 43000,
        "T4_HEART_UNDEAD": 62000
    }
    prices = mock_heart_prices or default_prices

    origin_heart_id = HEARTS_METADATA[origin]["item_id"]
    origin_price = prices.get(origin_heart_id, 45000)

    # 4. Avaliação de cada rota elegível
    routes_evaluated = []
    for dest in eligible_destinations:
        dest_heart_id = HEARTS_METADATA[dest]["item_id"]
        dest_price = prices.get(dest_heart_id, 45000)

        dist_cat, risk_zone = get_route_category(origin, dest)
        hearts_out = calculate_faction_route_reward(origin, dest, pack_size)
        trip_time_min = ROUND_TRIP_MINUTES_BENCHMARK.get(dist_cat, 12.0)

        decision_tree = simulate_post_trip_decision_tree(
            origin_city=origin,
            destination_city=dest,
            pack_size=pack_size,
            origin_heart_price=origin_price,
            destination_heart_price=dest_price,
            available_silver=available_silver,
            has_premium=has_premium,
            session_mode=guard["normalized_mode"]
        )

        tax_rate = 0.04 if has_premium else 0.08
        gross_return = hearts_out * dest_price
        net_return = int(gross_return * (1.0 - tax_rate))
        cost_in = pack_size * origin_price
        net_profit = net_return - cost_in
        roi_pct = round((net_profit / cost_in) * 100, 1) if cost_in > 0 else 0.0
        silver_per_hour = int((net_profit / trip_time_min) * 60) if trip_time_min > 0 else 0

        routes_evaluated.append({
            "destination_city": dest,
            "route_category": dist_cat,
            "risk_zone": risk_zone,
            "round_trip_minutes": trip_time_min,
            "hearts_in": pack_size,
            "hearts_out": hearts_out,
            "hearts_delta": hearts_out - pack_size,
            "destination_heart_name": HEARTS_METADATA[dest]["name_pt"],
            "financials": {
                "origin_heart_price": origin_price,
                "destination_heart_price": dest_price,
                "cost_in_silver": cost_in,
                "net_return_silver": net_return,
                "net_profit_silver": net_profit,
                "roi_pct": roi_pct,
                "silver_per_hour": silver_per_hour
            },
            "decision_tree": decision_tree
        })

    # Ranquear rotas por maior Prata / Hora
    routes_evaluated.sort(key=lambda x: x["financials"]["silver_per_hour"], reverse=True)
    best_route = routes_evaluated[0]

    return {
        "status": "SUCCESS",
        "origin_city": origin,
        "origin_heart": HEARTS_METADATA[origin],
        "pack_spec": pack_spec,
        "loadout_feasibility": {
            "target_weight_kg": target_weight_kg,
            "is_current_mount_sufficient": loadout_advice.get("is_current_mount_sufficient", False),
            "current_mount_eval": loadout_advice.get("current_mount_solution"),
            "cheapest_loadout_recommendation": loadout_advice.get("cheapest_loadout")
        },
        "session_mode": guard["normalized_mode"],
        "has_premium": has_premium,
        "best_route_recommended": best_route,
        "all_routes_ranked": routes_evaluated
    }
