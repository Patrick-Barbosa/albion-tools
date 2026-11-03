"""
Motor de Transporte de Facção e Economia de Corações (Faction Transport Engine) para Albion Online.

Implementa o ciclo oficial Round-Trip (entrega final na cidade de origem), a física
determinística de pesagem de fardos (125 kg, 668 kg, 1623 kg), topologia do Continente Real,
benchmark de tempo calibrado (Javali T5) e a árvore de decisão matemática dos 11 corações
(Recompra de Mercado vs Loops Perpétuos de Transmutação a 5.780 prata).
"""

from typing import Dict, Any, List, Optional, Tuple, Union
try:
    from .loadout_optimizer import solve_cheapest_loadout
except ImportError:
    from loadout_optimizer import solve_cheapest_loadout

# Identificadores oficiais dos corações de recurso no Albion Online (Tokens de Facção)
HEARTS_METADATA = {
    "Lymhurst": {
        "item_id": "T1_FACTION_FOREST_TOKEN_1",
        "legacy_id": "T4_HEART_WOOD",
        "name_pt": "Coração da Árvore (Arbóreo)",
        "name_en": "Treeheart",
        "resource": "Madeira / Floresta"
    },
    "Fort Sterling": {
        "item_id": "T1_FACTION_MOUNTAIN_TOKEN_1",
        "legacy_id": "T4_HEART_MOUNTAIN",
        "name_pt": "Coração da Montanha",
        "name_en": "Mountainheart",
        "resource": "Minério de Neve / Montanha"
    },
    "Bridgewatch": {
        "item_id": "T1_FACTION_STEPPE_TOKEN_1",
        "legacy_id": "T4_HEART_BEAST",
        "name_pt": "Coração da Fera",
        "name_en": "Beastheart",
        "resource": "Peles / Estepes"
    },
    "Thetford": {
        "item_id": "T1_FACTION_SWAMP_TOKEN_1",
        "legacy_id": "T4_HEART_SWAMP",
        "name_pt": "Coração do Pântano",
        "name_en": "Vineheart",
        "resource": "Fibras / Pântano"
    },
    "Martlock": {
        "item_id": "T1_FACTION_HIGHLAND_TOKEN_1",
        "legacy_id": "T4_HEART_ROCK",
        "name_pt": "Coração da Rocha",
        "name_en": "Rockheart",
        "resource": "Pedras / Planalto"
    },
    "Caerleon": {
        "item_id": "T1_FACTION_CAERLEON_TOKEN_1",
        "legacy_id": "T4_HEART_UNDEAD",
        "name_pt": "Coração Sombrio",
        "name_en": "Shadowheart",
        "resource": "Mercado Negro / Sombrio"
    }
}

# Identificadores oficiais e nomes das Capas por cidade e coração correspondente
FACTION_CAPE_METADATA = {
    "Lymhurst": {
        "item_id_base": "CAPEITEM_FW_LYMHURST",
        "name_pt": "Capa de Lymhurst",
        "crest_id": "T4_CREST_FW_LYMHURST",
        "city_heart_id": "T1_FACTION_FOREST_TOKEN_1",
        "city_heart_name": "Coração Arbóreo",
        "default_price_t4_2": 175000,
        "alternative_cape": {
            "item_id": "CAPEITEM_HERETIC",
            "name_pt": "Capa Herege",
            "crest_id": "T4_CREST_HERETIC",
            "default_price_t4_2": 185000
        }
    },
    "Fort Sterling": {
        "item_id_base": "CAPEITEM_FW_FORTSTERLING",
        "name_pt": "Capa de Fort Sterling",
        "crest_id": "T4_CREST_FW_FORTSTERLING",
        "city_heart_id": "T1_FACTION_MOUNTAIN_TOKEN_1",
        "city_heart_name": "Coração da Montanha",
        "default_price_t4_2": 160000,
        "alternative_cape": {
            "item_id": "CAPEITEM_UNDEAD",
            "name_pt": "Capa Morta-Viva",
            "crest_id": "T4_CREST_UNDEAD",
            "default_price_t4_2": 260000
        }
    },
    "Bridgewatch": {
        "item_id_base": "CAPEITEM_FW_BRIDGEWATCH",
        "name_pt": "Capa de Bridgewatch",
        "crest_id": "T4_CREST_FW_BRIDGEWATCH",
        "city_heart_id": "T1_FACTION_STEPPE_TOKEN_1",
        "city_heart_name": "Coração da Fera",
        "default_price_t4_2": 165000,
        "alternative_cape": {
            "item_id": "CAPEITEM_DEMON",
            "name_pt": "Capa Demoníaca",
            "crest_id": "T4_CREST_DEMON",
            "default_price_t4_2": 195000
        }
    },
    "Thetford": {
        "item_id_base": "CAPEITEM_FW_THETFORD",
        "name_pt": "Capa de Thetford",
        "crest_id": "T4_CREST_FW_THETFORD",
        "city_heart_id": "T1_FACTION_SWAMP_TOKEN_1",
        "city_heart_name": "Coração do Pântano",
        "default_price_t4_2": 170000,
        "alternative_cape": {
            "item_id": "CAPEITEM_MORGANA",
            "name_pt": "Capa de Morgana",
            "crest_id": "T4_CREST_MORGANA",
            "default_price_t4_2": 180000
        }
    },
    "Martlock": {
        "item_id_base": "CAPEITEM_FW_MARTLOCK",
        "name_pt": "Capa de Martlock",
        "crest_id": "T4_CREST_FW_MARTLOCK",
        "city_heart_id": "T1_FACTION_HIGHLAND_TOKEN_1",
        "city_heart_name": "Coração da Rocha",
        "default_price_t4_2": 160000,
        "alternative_cape": {
            "item_id": "CAPEITEM_KEEPER",
            "name_pt": "Capa do Guardião",
            "crest_id": "T4_CREST_KEEPER",
            "default_price_t4_2": 175000
        }
    },
    "Caerleon": {
        "item_id_base": "CAPEITEM_FW_CAERLEON",
        "name_pt": "Capa de Caerleon",
        "crest_id": "T4_CREST_FW_CAERLEON",
        "city_heart_id": "T1_FACTION_CAERLEON_TOKEN_1",
        "city_heart_name": "Coração Sombrio",
        "default_price_t4_2": 175000,
        "alternative_cape": {
            "item_id": "CAPEITEM_SMUGGLER",
            "name_pt": "Capa de Contrabandista",
            "crest_id": "T4_CAPEITEM_SMUGGLER_BP",
            "default_price_t4_2": 240000
        }
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


def build_cape_investment_audit(
    cape_name: str,
    cape_item_id: str,
    crest_name: str,
    crest_id: str,
    hearts_count: int,
    cape_sell_price: int,
    requires_transmutation: bool,
    tax_rate: float,
    cost_initial_pack: int,
    direct_net_profit: int,
    net_direct_revenue: int,
    material_prices: Dict[str, int]
) -> Dict[str, Any]:
    """
    Calcula o extrato detalhado de investimento adicional em insumos para confecção de capas,
    comparando diretamente o lucro da manufatura contra a venda pura dos corações recebidos.
    """
    def _fmt(val: Union[int, float]) -> str:
        return f"{int(val):,}".replace(",", ".")

    unit_cape_price = material_prices.get("T4_CAPE", 3642)
    unit_crest_price = material_prices.get(crest_id, 11976 if "SMUGGLER" in crest_id else 15000)
    unit_rune_price = material_prices.get("T4_RUNE", 8)
    unit_soul_price = material_prices.get("T4_SOUL", 82)

    unit_runes_96 = unit_rune_price * 96
    unit_souls_96 = unit_soul_price * 96
    unit_transmute = TRANSMUTE_FEE_SILVER if requires_transmutation else 0

    unit_inputs_total = unit_cape_price + unit_crest_price + unit_runes_96 + unit_souls_96 + unit_transmute
    batch_additional_investment = hearts_count * unit_inputs_total

    # Faturamento e lucro líquido das capas vendidas no mercado local
    gross_cape_revenue = hearts_count * cape_sell_price
    market_tax_rate = tax_rate + 0.025
    net_cape_revenue = int(gross_cape_revenue * (1.0 - market_tax_rate))
    total_cape_cost = cost_initial_pack + batch_additional_investment
    net_cape_profit = net_cape_revenue - total_cape_cost

    delta_profit_vs_direct = net_cape_profit - direct_net_profit
    roi_on_extra_capital_pct = round((delta_profit_vs_direct / batch_additional_investment) * 100, 1) if batch_additional_investment > 0 else 0.0

    transmute_row = (
        f"| **Taxa Transmutação NPC** | 1x ({_fmt(TRANSMUTE_FEE_SILVER)} 🪙) | {hearts_count}x | {_fmt(TRANSMUTE_FEE_SILVER)} 🪙 | {_fmt(hearts_count * TRANSMUTE_FEE_SILVER)} 🪙 |\n"
        if requires_transmutation else ""
    )

    percent_gain = round((delta_profit_vs_direct / direct_net_profit * 100), 1) if direct_net_profit > 0 else 0.0
    sign = "+" if delta_profit_vs_direct >= 0 else ""

    cape_investment_markdown = (
        f"### 🧵 Detalhamento do Investimento Adicional em Insumos ({cape_name} T4.2)\n\n"
        f"Para fabricar e vender o lote de **{hearts_count}x {cape_name} T4.2** no mercado local, você precisará desembolsar do seu saldo bancário:\n\n"
        f"| Insumo Necessário | Qtd por Capa | Qtd Lote ({hearts_count}x) | Cotação Unitária | Subtotal Insumo |\n"
        f"| :--- | :--- | :--- | :--- | :--- |\n"
        f"| **Capa Comum T4** (`T4_CAPE`) | 1x | {hearts_count}x | {_fmt(unit_cape_price)} 🪙 | {_fmt(hearts_count * unit_cape_price)} 🪙 |\n"
        f"| **{crest_name}** (`{crest_id}`) | 1x | {hearts_count}x | {_fmt(unit_crest_price)} 🪙 | {_fmt(hearts_count * unit_crest_price)} 🪙 |\n"
        f"| **Runas T4 (.1)** (`T4_RUNE`) | 96x | {_fmt(hearts_count * 96)}x | {_fmt(unit_rune_price)} 🪙 | {_fmt(hearts_count * unit_runes_96)} 🪙 |\n"
        f"| **Almas T4 (.2)** (`T4_SOUL`) | 96x | {_fmt(hearts_count * 96)}x | {_fmt(unit_soul_price)} 🪙 | {_fmt(hearts_count * unit_souls_96)} 🪙 |\n"
        f"{transmute_row}"
        f"| **TOTAL INVESTIMENTO ADICIONAL** | — | — | **{_fmt(unit_inputs_total)} 🪙/capa** | **{_fmt(batch_additional_investment)} 🪙** |\n\n"
        f"#### 📊 Comparativo: Venda Direta dos Corações vs Manufatura de {cape_name} T4.2\n\n"
        f"| Métrica Financeira | 1. Venda Direta dos Corações | 2. Manufatura de Capas ({cape_name}) | Saldo / Vantagem Líquida (Delta) |\n"
        f"| :--- | :--- | :--- | :--- |\n"
        f"| **Investimento Extra em Insumos** | 0 🪙 | {_fmt(batch_additional_investment)} 🪙 | -{_fmt(batch_additional_investment)} 🪙 (Capital necessário) |\n"
        f"| **Faturamento Líquido (após taxas)** | {_fmt(net_direct_revenue)} 🪙 | {_fmt(net_cape_revenue)} 🪙 | +{_fmt(net_cape_revenue - net_direct_revenue)} 🪙 |\n"
        f"| **Lucro Líquido Limpo no Bolso** | {_fmt(direct_net_profit)} 🪙 | {_fmt(net_cape_profit)} 🪙 | **{sign}{_fmt(delta_profit_vs_direct)} 🪙** ({sign}{percent_gain}% de lucro) |\n"
        f"| **ROI do Capital Adicional Investido** | — | — | **+{roi_on_extra_capital_pct}%** de retorno sobre o extra |\n"
    )

    return {
        "cape_name": cape_name,
        "cape_item_id": cape_item_id,
        "crest_id": crest_id,
        "crest_name": crest_name,
        "requires_transmutation": requires_transmutation,
        "unit_materials": {
            "regular_cape_silver": unit_cape_price,
            "crest_or_ornament_silver": unit_crest_price,
            "runes_96_silver": unit_runes_96,
            "souls_96_silver": unit_souls_96,
            "transmute_fee_silver": unit_transmute,
            "total_unit_inputs_silver": unit_inputs_total
        },
        "batch_totals": {
            "hearts_used": hearts_count,
            "regular_capes_total": hearts_count * unit_cape_price,
            "crests_total": hearts_count * unit_crest_price,
            "runes_total": hearts_count * unit_runes_96,
            "souls_total": hearts_count * unit_souls_96,
            "transmute_total": hearts_count * unit_transmute,
            "total_additional_investment_silver": batch_additional_investment
        },
        "financial_comparison": {
            "initial_pack_cost_silver": cost_initial_pack,
            "cape_sell_price_unit": cape_sell_price,
            "gross_cape_revenue_silver": gross_cape_revenue,
            "net_cape_revenue_silver": net_cape_revenue,
            "net_cape_profit_silver": net_cape_profit,
            "direct_raw_hearts_profit_silver": direct_net_profit,
            "delta_extra_profit_silver": delta_profit_vs_direct,
            "roi_on_additional_investment_pct": roi_on_extra_capital_pct
        },
        "markdown_table": cape_investment_markdown
    }


def simulate_post_trip_decision_tree(
    origin_city: str,
    destination_city: str,
    pack_size: int,
    origin_heart_price: int,
    destination_heart_price: int,
    available_silver: int,
    has_premium: bool,
    session_mode: str,
    cape_market_price: Optional[int] = None,
    trip_time_min: float = 10.0,
    material_prices: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """
    Simula e RANQUEIA de forma cabrita e definitiva as 4 opções pós-viagem para o jogador:
    1. Loop Autossustentável (Giro Rápido Sem Gastar Saldo Bancário)
    2. Venda Direta dos Corações no Mercado Municipal da Cidade de Origem
    3. Manufatura de Capas da Facção da Cidade de Origem (T4.2)
    4. Expansão Perpétua / Transmutação Total para Corações da Cidade

    Define com clareza absoluta ONDE vender (sempre na cidade de origem) e QUAL capa fazer.
    """
    hearts_in = pack_size
    hearts_out = calculate_faction_route_reward(origin_city, destination_city, pack_size)
    tax_rate = 0.04 if has_premium else 0.08

    is_caerleon = (destination_city.lower() == "caerleon")
    origin_heart_info = HEARTS_METADATA.get(origin_city, HEARTS_METADATA["Lymhurst"])
    dest_heart_info = HEARTS_METADATA.get(destination_city, HEARTS_METADATA["Caerleon"])
    cost_initial_pack = hearts_in * origin_heart_price
    surplus_hearts_count = hearts_out - hearts_in

    def _fmt(val: Union[int, float]) -> str:
        return f"{int(val):,}".replace(",", ".")

    mat_prices = material_prices or {}
    unit_cape_base = mat_prices.get("T4_CAPE", 3642)
    unit_rune = mat_prices.get("T4_RUNE", 8) * 96
    unit_soul = mat_prices.get("T4_SOUL", 82) * 96

    # ─────────────────────────────────────────────────────────────
    # ESTRATÉGIA 2: Venda Direta dos Corações no Mercado de Origem
    # ─────────────────────────────────────────────────────────────
    gross_direct_revenue = hearts_out * destination_heart_price
    net_direct_revenue = int(gross_direct_revenue * (1.0 - tax_rate))
    direct_net_profit = net_direct_revenue - cost_initial_pack
    direct_silver_per_hour = int((direct_net_profit / trip_time_min) * 60) if trip_time_min > 0 else 0

    direct_strat = {
        "strategy_id": "DIRECT_SALE_ORIGIN_MARKET",
        "title": f"Venda Direta dos Corações no Mercado de {origin_city}",
        "net_profit_per_trip": direct_net_profit,
        "silver_per_hour": direct_silver_per_hour,
        "effort_level": "Médio (Depende de ordens de venda)",
        "summary": (
            f"Venda todos os {hearts_out} {dest_heart_info['name_pt']} no Mercado Municipal de {origin_city}. "
            f"Gera {_fmt(direct_net_profit)} 🪙 de lucro limpo, mas você precisa recomprar novo fardo de {hearts_in} "
            f"{origin_heart_info['name_pt']} com a prata gerada se quiser viajar de novo."
        )
    }

    if is_caerleon:
        # =========================================================================
        # CENÁRIO A: Rota para Caerleon (Recebe Corações Sombrios)
        # =========================================================================
        # 1. Loop Autossustentável via Transmutação (5.780 🪙/coração no NPC natal)
        transmute_fee_next_trip = hearts_in * TRANSMUTE_FEE_SILVER
        gross_surplus_sale = surplus_hearts_count * destination_heart_price
        net_surplus_sale = int(gross_surplus_sale * (1.0 - tax_rate))
        net_cash_in_pocket = net_surplus_sale - transmute_fee_next_trip
        cash_per_hour = int((net_cash_in_pocket / trip_time_min) * 60) if trip_time_min > 0 else 0

        autoloop_strat = {
            "strategy_id": "AUTOLOOP_HYBRID",
            "title": "Loop Autossustentável (Giro Rápido Sem Parar)",
            "net_profit_per_trip": net_cash_in_pocket,
            "silver_per_hour": cash_per_hour,
            "effort_level": "Baixo (Imediato)",
            "summary": (
                f"Transmute {hearts_in} corações sombrios pagando {_fmt(transmute_fee_next_trip)} 🪙 no transmutador de {origin_city} "
                f"para reiniciar o transporte imediatamente. Venda os {surplus_hearts_count} corações sombrios excedentes no "
                f"Mercado de {origin_city} e embolse {_fmt(net_cash_in_pocket)} 🪙 de prata líquida a cada {trip_time_min:.0f} min."
            )
        }

        # 2. Transmutação Total (Expansão Perpétua)
        total_transmute_fee = hearts_out * TRANSMUTE_FEE_SILVER
        gross_origin_hearts_rev = hearts_out * origin_heart_price
        net_origin_hearts_rev = int(gross_origin_hearts_rev * (1.0 - tax_rate))
        transmute_net_profit = net_origin_hearts_rev - total_transmute_fee - cost_initial_pack

        expansion_strat = {
            "strategy_id": "PERPETUAL_EXPANSION_STORE",
            "title": f"Transmutar Todos em {origin_heart_info['name_pt']} e Vender Puro",
            "net_profit_per_trip": transmute_net_profit,
            "silver_per_hour": int((transmute_net_profit / trip_time_min) * 60) if trip_time_min > 0 else 0,
            "effort_level": "Baixo",
            "summary": (
                f"Transmute todos os {hearts_out} sombrios em {origin_heart_info['name_pt']} pagando {_fmt(total_transmute_fee)} 🪙. "
                f"Lucro líquido: {_fmt(transmute_net_profit)} 🪙. "
                f"{'🔴 NÃO COMPENSA: Vender o sombrio direto dá mais lucro!' if transmute_net_profit < direct_net_profit else '🟢 Rentável.'}"
            )
        }

        # 3. Manufatura de Capas: 2 Caminhos (Transmutadas da Origem vs Diretas de Caerleon)
        origin_cape_meta = FACTION_CAPE_METADATA.get(origin_city, FACTION_CAPE_METADATA["Lymhurst"])
        origin_cape_name = origin_cape_meta["name_pt"]
        origin_alt_meta = origin_cape_meta.get("alternative_cape")

        origin_crest_p = mat_prices.get(origin_cape_meta["crest_id"], 15000)
        origin_non_heart_cost = unit_cape_base + origin_crest_p + unit_rune + unit_soul

        effective_cape_sell_price = cape_market_price or mat_prices.get(f"T4_{origin_cape_meta['item_id_base']}@2") or origin_cape_meta["default_price_t4_2"]
        net_cape_revenue_unit = int(effective_cape_sell_price * (1.0 - tax_rate - 0.025))
        transmute_fee_per_cape = TRANSMUTE_FEE_SILVER
        unit_cape_craft_cost = origin_non_heart_cost + transmute_fee_per_cape + origin_heart_price
        unit_cape_profit = net_cape_revenue_unit - unit_cape_craft_cost
        total_cape_profit = (net_cape_revenue_unit - origin_non_heart_cost - transmute_fee_per_cape) * hearts_out - cost_initial_pack
        cape_silver_per_hour = int((total_cape_profit / (trip_time_min + 15.0)) * 60)

        origin_cape_audit = build_cape_investment_audit(
            cape_name=origin_cape_name,
            cape_item_id=f"T4_{origin_cape_meta['item_id_base']}@2",
            crest_name=f"Brasão de {origin_city}",
            crest_id=origin_cape_meta["crest_id"],
            hearts_count=hearts_out,
            cape_sell_price=effective_cape_sell_price,
            requires_transmutation=True,
            tax_rate=tax_rate,
            cost_initial_pack=cost_initial_pack,
            direct_net_profit=direct_net_profit,
            net_direct_revenue=net_direct_revenue,
            material_prices=mat_prices
        )

        # Capa Alternativa da Cidade Natal (ex: Capa Herege)
        alt_cape_info = None
        origin_alt_audit = None
        total_alt_profit = -999999999
        if origin_alt_meta:
            alt_crest_p = mat_prices.get(origin_alt_meta["crest_id"], 18000)
            origin_alt_non_heart_cost = unit_cape_base + alt_crest_p + unit_rune + unit_soul
            alt_sell_price = mat_prices.get(f"T4_{origin_alt_meta['item_id']}@2") or origin_alt_meta.get("default_price_t4_2", 185000)
            net_alt_revenue_unit = int(alt_sell_price * (1.0 - tax_rate - 0.025))
            unit_alt_craft_cost = origin_alt_non_heart_cost + transmute_fee_per_cape + origin_heart_price
            unit_alt_profit = net_alt_revenue_unit - unit_alt_craft_cost
            total_alt_profit = (net_alt_revenue_unit - origin_alt_non_heart_cost - transmute_fee_per_cape) * hearts_out - cost_initial_pack

            origin_alt_audit = build_cape_investment_audit(
                cape_name=origin_alt_meta["name_pt"],
                cape_item_id=f"T4_{origin_alt_meta['item_id']}@2",
                crest_name=f"Brasão {origin_alt_meta['name_pt']}",
                crest_id=origin_alt_meta["crest_id"],
                hearts_count=hearts_out,
                cape_sell_price=alt_sell_price,
                requires_transmutation=True,
                tax_rate=tax_rate,
                cost_initial_pack=cost_initial_pack,
                direct_net_profit=direct_net_profit,
                net_direct_revenue=net_direct_revenue,
                material_prices=mat_prices
            )

            alt_cape_info = {
                "item_id": origin_alt_meta["item_id"],
                "cape_name": origin_alt_meta["name_pt"],
                "crest_id": origin_alt_meta["crest_id"],
                "estimated_sale_price": alt_sell_price,
                "net_profit_per_cape": unit_alt_profit,
                "total_batch_profit": total_alt_profit,
                "delta_profit_vs_royal_cape": total_alt_profit - total_cape_profit,
                "cape_investment_audit": origin_alt_audit
            }

        # Opções Diretas de Caerleon (ZERO Taxa de Transmutação)
        caerleon_cape_meta = FACTION_CAPE_METADATA["Caerleon"]
        caerleon_alt_meta = caerleon_cape_meta.get("alternative_cape")
        caerleon_crest_p = mat_prices.get(caerleon_cape_meta["crest_id"], 16000)
        caerleon_non_heart_cost = unit_cape_base + caerleon_crest_p + unit_rune + unit_soul
        caerleon_sell_p = mat_prices.get(f"T4_{caerleon_cape_meta['item_id_base']}@2") or caerleon_cape_meta["default_price_t4_2"]
        net_caerleon_rev = int(caerleon_sell_p * (1.0 - tax_rate - 0.025))
        total_caerleon_profit = (net_caerleon_rev - caerleon_non_heart_cost) * hearts_out - cost_initial_pack

        caerleon_audit = build_cape_investment_audit(
            cape_name=caerleon_cape_meta["name_pt"],
            cape_item_id=f"T4_{caerleon_cape_meta['item_id_base']}@2",
            crest_name="Brasão de Caerleon",
            crest_id=caerleon_cape_meta["crest_id"],
            hearts_count=hearts_out,
            cape_sell_price=caerleon_sell_p,
            requires_transmutation=False,
            tax_rate=tax_rate,
            cost_initial_pack=cost_initial_pack,
            direct_net_profit=direct_net_profit,
            net_direct_revenue=net_direct_revenue,
            material_prices=mat_prices
        )

        smuggler_crest_id = caerleon_alt_meta["crest_id"] if caerleon_alt_meta else "T4_CAPEITEM_SMUGGLER_BP"
        smuggler_bp_p = mat_prices.get(smuggler_crest_id, 11976)
        smuggler_non_heart_cost = unit_cape_base + smuggler_bp_p + unit_rune + unit_soul
        smuggler_sell_p = mat_prices.get("T4_CAPEITEM_SMUGGLER@2") or (caerleon_alt_meta["default_price_t4_2"] if caerleon_alt_meta else 240000)
        net_smuggler_rev = int(smuggler_sell_p * (1.0 - tax_rate - 0.025))
        total_smuggler_profit = (net_smuggler_rev - smuggler_non_heart_cost) * hearts_out - cost_initial_pack

        smuggler_audit = build_cape_investment_audit(
            cape_name=caerleon_alt_meta["name_pt"] if caerleon_alt_meta else "Capa de Contrabandista",
            cape_item_id="T4_CAPEITEM_SMUGGLER@2",
            crest_name="Ornamento de Contrabandista",
            crest_id=smuggler_crest_id,
            hearts_count=hearts_out,
            cape_sell_price=smuggler_sell_p,
            requires_transmutation=False,
            tax_rate=tax_rate,
            cost_initial_pack=cost_initial_pack,
            direct_net_profit=direct_net_profit,
            net_direct_revenue=net_direct_revenue,
            material_prices=mat_prices
        )

        caerleon_direct_options = [
            {
                "cape_name": caerleon_cape_meta["name_pt"],
                "item_id": caerleon_cape_meta["item_id_base"],
                "estimated_sale_price": caerleon_sell_p,
                "total_batch_profit": total_caerleon_profit,
                "requires_transmutation": False,
                "advantage_over_origin_royal": total_caerleon_profit - total_cape_profit,
                "cape_investment_audit": caerleon_audit
            },
            {
                "cape_name": caerleon_alt_meta["name_pt"] if caerleon_alt_meta else "Capa de Contrabandista",
                "item_id": caerleon_alt_meta["item_id"] if caerleon_alt_meta else "CAPEITEM_SMUGGLER",
                "estimated_sale_price": smuggler_sell_p,
                "total_batch_profit": total_smuggler_profit,
                "requires_transmutation": False,
                "advantage_over_origin_royal": total_smuggler_profit - total_cape_profit,
                "cape_investment_audit": smuggler_audit
            }
        ]

        # Ranking de todas as 4 opções
        cape_candidates = [
            (origin_cape_name, total_cape_profit, origin_cape_audit),
            (origin_alt_meta["name_pt"] if origin_alt_meta else "", total_alt_profit, origin_alt_audit),
            (caerleon_cape_meta["name_pt"], total_caerleon_profit, caerleon_audit),
            (caerleon_alt_meta["name_pt"] if caerleon_alt_meta else "", total_smuggler_profit, smuggler_audit)
        ]
        best_cape_name, best_cape_profit, best_cape_audit = max(cape_candidates, key=lambda x: x[1])

        cape_strat = {
            "strategy_id": "CAPE_MANUFACTURING",
            "title": f"Manufatura de {origin_cape_name} T4.2 no Mercado de {origin_city}",
            "net_profit_per_trip": total_cape_profit,
            "silver_per_hour": cape_silver_per_hour,
            "effort_level": "Alto (Requer comprar capas/brasões/runas e aguardar venda)",
            "summary": (
                f"Transmute os corações em {origin_cape_meta['city_heart_name']} pagando {_fmt(TRANSMUTE_FEE_SILVER)} 🪙 cada "
                f"e confeccione {hearts_out}x {origin_cape_name} T4.2 no Mercado de {origin_city}, lucrando {_fmt(total_cape_profit)} 🪙 "
                f"({_fmt(unit_cape_profit)} 🪙/capa). "
                f"💡 DICA DE OURO (2 CAMINHOS): Como você recebeu Corações Sombrios, você pode fabricar DIRETO a "
                f"{caerleon_alt_meta['name_pt']} (ZERO taxa de transmutação, gerando {_fmt(total_smuggler_profit)} 🪙 de lucro!) "
                f"ou transmutar para {origin_alt_meta['name_pt']} ({_fmt(total_alt_profit)} 🪙). "
                f"A campeã absoluta é a '{best_cape_name}' ({_fmt(best_cape_profit)} 🪙 de lucro líquido)!\n\n"
                f"💰 Investimento Adicional em Insumos: {_fmt(best_cape_audit['batch_totals']['total_additional_investment_silver'])} 🪙 "
                f"({_fmt(best_cape_audit['unit_materials']['total_unit_inputs_silver'])} 🪙/capa). "
                f"Gera +{_fmt(best_cape_audit['financial_comparison']['delta_extra_profit_silver'])} 🪙 a mais que a venda direta "
                f"(ROI de +{best_cape_audit['financial_comparison']['roi_on_additional_investment_pct']}% sobre o capital extra)."
            )
        }

        recommended_cape_dict = {
            "city": origin_city,
            "cape_name": origin_cape_name,
            "tier_recommended": "T4.2",
            "recipe": f"1x Capa Comum T4 + 1x {origin_cape_meta['crest_id']} + 1x {origin_cape_meta['city_heart_name']} + 96x Runa T4 + 96x Alma T4",
            "estimated_sale_price": effective_cape_sell_price,
            "net_profit_per_cape": unit_cape_profit,
            "total_batch_profit": total_cape_profit,
            "alternative_cape": alt_cape_info,
            "caerleon_direct_options": caerleon_direct_options,
            "best_cape_overall": best_cape_name,
            "best_cape_overall_profit": best_cape_profit,
            "cape_investment_audit": best_cape_audit,
            "cape_investment_markdown": best_cape_audit["markdown_table"]
        }
        selected_cape_audit = best_cape_audit
        selected_cape_markdown = best_cape_audit["markdown_table"]

    else:
        # =========================================================================
        # CENÁRIO B: Rota entre Cidades Reais (Recebe Corações da Cidade de Destino)
        # =========================================================================
        # REGRA OFICIAL DE JOGO: Em Albion Online, o NPC NÃO transmuta entre corações reais!
        # Corações da Montanha não podem ser transmutados para Corações Arbóreos.
        # Portanto, o jogador só pode fabricar capas da CIDADE DE DESTINO com esses corações!
        dest_cape_meta = FACTION_CAPE_METADATA.get(destination_city, FACTION_CAPE_METADATA["Fort Sterling"])
        dest_cape_name = dest_cape_meta["name_pt"]
        dest_alt_meta = dest_cape_meta.get("alternative_cape")

        dest_crest_p = mat_prices.get(dest_cape_meta["crest_id"], 15000)
        dest_non_heart_cost = unit_cape_base + dest_crest_p + unit_rune + unit_soul

        dest_cape_sell_price = cape_market_price or mat_prices.get(f"T4_{dest_cape_meta['item_id_base']}@2") or dest_cape_meta["default_price_t4_2"]
        net_dest_cape_rev = int(dest_cape_sell_price * (1.0 - tax_rate - 0.025))
        unit_dest_craft_cost = dest_non_heart_cost + destination_heart_price
        unit_cape_profit = net_dest_cape_rev - unit_dest_craft_cost
        total_cape_profit = (net_dest_cape_rev - dest_non_heart_cost) * hearts_out - cost_initial_pack
        cape_silver_per_hour = int((total_cape_profit / (trip_time_min + 15.0)) * 60)

        dest_cape_audit = build_cape_investment_audit(
            cape_name=dest_cape_name,
            cape_item_id=f"T4_{dest_cape_meta['item_id_base']}@2",
            crest_name=f"Brasão de {destination_city}",
            crest_id=dest_cape_meta["crest_id"],
            hearts_count=hearts_out,
            cape_sell_price=dest_cape_sell_price,
            requires_transmutation=False,
            tax_rate=tax_rate,
            cost_initial_pack=cost_initial_pack,
            direct_net_profit=direct_net_profit,
            net_direct_revenue=net_direct_revenue,
            material_prices=mat_prices
        )

        # Alternativa do Destino (ex: Capa Morta-Viva)
        dest_alt_info = None
        alt_dest_tip = ""
        dest_alt_audit = None
        total_dest_alt_profit = -999999999
        if dest_alt_meta:
            dest_alt_crest_p = mat_prices.get(dest_alt_meta["crest_id"], 22000)
            dest_alt_non_heart_cost = unit_cape_base + dest_alt_crest_p + unit_rune + unit_soul
            alt_sell_p = mat_prices.get(f"T4_{dest_alt_meta['item_id']}@2") or dest_alt_meta.get("default_price_t4_2", 200000)
            net_dest_alt_rev = int(alt_sell_p * (1.0 - tax_rate - 0.025))
            unit_dest_alt_craft_cost = dest_alt_non_heart_cost + destination_heart_price
            unit_dest_alt_profit = net_dest_alt_rev - unit_dest_alt_craft_cost
            total_dest_alt_profit = (net_dest_alt_rev - dest_alt_non_heart_cost) * hearts_out - cost_initial_pack
            delta_dest = total_dest_alt_profit - total_cape_profit

            dest_alt_audit = build_cape_investment_audit(
                cape_name=dest_alt_meta["name_pt"],
                cape_item_id=f"T4_{dest_alt_meta['item_id']}@2",
                crest_name=f"Brasão {dest_alt_meta['name_pt']}",
                crest_id=dest_alt_meta["crest_id"],
                hearts_count=hearts_out,
                cape_sell_price=alt_sell_p,
                requires_transmutation=False,
                tax_rate=tax_rate,
                cost_initial_pack=cost_initial_pack,
                direct_net_profit=direct_net_profit,
                net_direct_revenue=net_direct_revenue,
                material_prices=mat_prices
            )

            dest_alt_info = {
                "item_id": dest_alt_meta["item_id"],
                "cape_name": dest_alt_meta["name_pt"],
                "crest_id": dest_alt_meta["crest_id"],
                "estimated_sale_price": alt_sell_p,
                "net_profit_per_cape": unit_dest_alt_profit,
                "total_batch_profit": total_dest_alt_profit,
                "delta_profit_vs_royal_cape": delta_dest,
                "cape_investment_audit": dest_alt_audit
            }
            if delta_dest > 0:
                alt_dest_tip = (
                    f" 💡 DICA DE OURO: Você também pode fabricar a {dest_alt_meta['name_pt']} T4.2 usando o mesmo "
                    f"{dest_cape_meta['city_heart_name']}! Vendendo no Mercado de {origin_city} a {_fmt(alt_sell_p)} 🪙, "
                    f"ela rende {_fmt(total_dest_alt_profit)} 🪙 (+{_fmt(delta_dest)} 🪙 a mais que a {dest_cape_name})!"
                )

        if dest_alt_meta and total_dest_alt_profit > total_cape_profit:
            best_dest_audit = dest_alt_audit
            best_dest_cape_name = dest_alt_meta["name_pt"]
            best_dest_profit = total_dest_alt_profit
        else:
            best_dest_audit = dest_cape_audit
            best_dest_cape_name = dest_cape_name
            best_dest_profit = total_cape_profit

        cape_strat = {
            "strategy_id": "CAPE_MANUFACTURING",
            "title": f"Manufatura de {dest_cape_name} T4.2 no Mercado de {origin_city}",
            "net_profit_per_trip": total_cape_profit,
            "silver_per_hour": cape_silver_per_hour,
            "effort_level": "Alto (Requer comprar capas/brasões/runas e aguardar venda)",
            "summary": (
                f"Como você recebeu {dest_cape_meta['city_heart_name']} e em Albion Online NÃO existe transmutação entre corações reais, "
                f"você só pode fabricar capas de {destination_city}! Confeccione {hearts_out}x {dest_cape_name} T4.2 e venda "
                f"no Mercado Municipal de {origin_city} a {_fmt(dest_cape_sell_price)} 🪙 cada, lucrando {_fmt(total_cape_profit)} 🪙 "
                f"({_fmt(unit_cape_profit)} 🪙/capa).{alt_dest_tip}\n\n"
                f"💰 Investimento Adicional em Insumos: {_fmt(best_dest_audit['batch_totals']['total_additional_investment_silver'])} 🪙 "
                f"({_fmt(best_dest_audit['unit_materials']['total_unit_inputs_silver'])} 🪙/capa). "
                f"Gera +{_fmt(best_dest_audit['financial_comparison']['delta_extra_profit_silver'])} 🪙 a mais que a venda direta "
                f"(ROI de +{best_dest_audit['financial_comparison']['roi_on_additional_investment_pct']}% sobre o capital extra)."
            )
        }

        recommended_cape_dict = {
            "city": destination_city,
            "cape_name": dest_cape_name,
            "tier_recommended": "T4.2",
            "recipe": f"1x Capa Comum T4 + 1x {dest_cape_meta['crest_id']} + 1x {dest_cape_meta['city_heart_name']} + 96x Runa T4 + 96x Alma T4",
            "estimated_sale_price": dest_cape_sell_price,
            "net_profit_per_cape": unit_cape_profit,
            "total_batch_profit": total_cape_profit,
            "alternative_cape": dest_alt_info,
            "transmutation_available": False,
            "transmutation_note": (
                f"Em Albion Online, o NPC municipal de transmutação só aceita Corações Sombrios de Caerleon. "
                f"Corações de {destination_city} não podem ser transmutados para corações de {origin_city}. "
                f"Portanto, as capas produzíveis com esta rota são restritas às de {destination_city} "
                f"({dest_cape_name} e {dest_alt_meta['name_pt'] if dest_alt_meta else ''})."
            ),
            "cape_investment_audit": best_dest_audit,
            "cape_investment_markdown": best_dest_audit["markdown_table"]
        }
        selected_cape_audit = best_dest_audit
        selected_cape_markdown = best_dest_audit["markdown_table"]

        # 1. Loop de Recompra no Mercado Local
        gross_dest_sale = hearts_out * destination_heart_price
        net_dest_sale = int(gross_dest_sale * (1.0 - tax_rate))
        cost_rebuy_pack = hearts_in * origin_heart_price
        net_cash_in_pocket = net_dest_sale - cost_rebuy_pack
        cash_per_hour = int((net_cash_in_pocket / trip_time_min) * 60) if trip_time_min > 0 else 0

        autoloop_strat = {
            "strategy_id": "AUTOLOOP_HYBRID",
            "title": f"Loop de Recompra no Mercado de {origin_city}",
            "net_profit_per_trip": net_cash_in_pocket,
            "silver_per_hour": cash_per_hour,
            "effort_level": "Baixo (Giro de Mercado)",
            "summary": (
                f"Como não existe transmutação entre corações de cidades reais, venda os {hearts_out} {dest_cape_meta['city_heart_name']} "
                f"no Mercado Municipal de {origin_city} (arrecadando {_fmt(net_dest_sale)} 🪙) e recompre {hearts_in} "
                f"{origin_heart_info['name_pt']} ({_fmt(cost_rebuy_pack)} 🪙) para reiniciar a viagem. "
                f"Lucro líquido vivo no bolso: {_fmt(net_cash_in_pocket)} 🪙 a cada {trip_time_min:.0f} min."
            )
        }

        # 4. Venda Paciente com Ordem de Venda dos Corações Recebidos (+15% margem)
        patient_sell_price = int(destination_heart_price * 1.15)
        patient_net_rev = int(hearts_out * patient_sell_price * (1.0 - tax_rate - 0.025))
        patient_net_profit = patient_net_rev - cost_initial_pack

        expansion_strat = {
            "strategy_id": "PERPETUAL_EXPANSION_STORE",
            "title": f"Venda Paciente dos Corações de {destination_city} (+15% Margem)",
            "net_profit_per_trip": patient_net_profit,
            "silver_per_hour": int((patient_net_profit / (trip_time_min + 60.0)) * 60),
            "effort_level": "Médio (Aguardar preenchimento de ordem)",
            "summary": (
                f"Coloque todos os {hearts_out} {dest_cape_meta['city_heart_name']} em Ordem de Venda no Mercado de {origin_city} "
                f"a {_fmt(patient_sell_price)} 🪙 cada (+15% acima da venda imediata). "
                f"Lucro líquido: {_fmt(patient_net_profit)} 🪙. (Transmutação indisponível para corações de cidades reais)."
            )
        }

    # ─────────────────────────────────────────────────────────────
    # RANKING COMPARATIVO CABRITO (Ordenado por Lucro Líquido Real)
    # ─────────────────────────────────────────────────────────────
    ranked_list = [autoloop_strat, direct_strat, cape_strat, expansion_strat]
    ranked_list.sort(key=lambda x: x["net_profit_per_trip"], reverse=True)
    for idx, item in enumerate(ranked_list, 1):
        item["rank"] = idx

    # Veredito Definitivo
    if session_mode == "CONTINUOUS_LOOP":
        if is_caerleon:
            definitive_verdict = (
                f"👉 VEREDITO DEFINITIVO (Giro Rápido): Escolha o LOOP AUTOSSUSTENTÁVEL! "
                f"Ao retornar a {origin_city}, vá ao transmutador municipal e transforme {hearts_in} corações sombrios "
                f"em {hearts_in} {origin_heart_info['name_pt']} (custa {_fmt(transmute_fee_next_trip)} 🪙 de taxa). "
                f"Com isso, seu fardo de {hearts_in} corações já está pronto para a próxima viagem sem tirar prata do banco. "
                f"Em seguida, venda os {surplus_hearts_count} corações sombrios excedentes no Mercado de {origin_city} "
                f"e embolse {_fmt(net_cash_in_pocket)} 🪙 de prata líquida viva no bolso a cada {trip_time_min:.0f} minutos "
                f"(rendimento estimado de {_fmt(cash_per_hour)} 🪙/hora)."
            )
        else:
            definitive_verdict = (
                f"👉 VEREDITO DEFINITIVO (Giro Rápido em Rota Segura): Escolha o LOOP DE RECOMPRA NO MERCADO! "
                f"Como o sistema de Albion Online NÃO transmuta corações entre cidades reais (apenas Corações Sombrios podem ser transmutados), "
                f"venda os {hearts_out} {dest_heart_info['name_pt']} no Mercado de {origin_city} e utilize parte do saldo para "
                f"recomprar {hearts_in} {origin_heart_info['name_pt']} para reiniciar a rota. "
                f"Você embolsa {_fmt(net_cash_in_pocket)} 🪙 de lucro líquido livre a cada {trip_time_min:.0f} minutos "
                f"(rendimento estimado de {_fmt(cash_per_hour)} 🪙/hora)."
            )
    else:
        best_opt = ranked_list[0]
        definitive_verdict = (
            f"👉 VEREDITO DEFINITIVO (Lucro Máximo / Paciente): A opção mais lucrativa em prata absoluta é "
            f"'{best_opt['title']}', gerando {_fmt(best_opt['net_profit_per_trip'])} 🪙 de lucro líquido total por viagem. "
            f"Toda a negociação e fabricação deve ocorrer 100% no Mercado de {origin_city}."
        )

    return {
        "hearts_in": hearts_in,
        "hearts_out": hearts_out,
        "net_hearts_delta": surplus_hearts_count,
        "is_caerleon": is_caerleon,
        "operational_protocol": {
            "origin_city": origin_city,
            "destination_city": destination_city,
            "where_to_sell": f"Mercado Municipal de {origin_city}",
            "where_to_transmute": f"Transmutador Municipal de {origin_city}",
            "critical_rules": [
                f"1. NUNCA tente entrar em Caerleon nem em outra capital real durante o transporte! A entrega do fardo é no Contrabandista (Smuggler) no posto avançado no mapa aberto.",
                f"2. Entrar em uma cidade estrangeira cancela o faccionamento e DESTROI o fardo de corações.",
                f"3. Após falar com o contrabandista, retorne imediatamente para {origin_city}.",
                f"4. A entrega final e o resgate da recompensa são feitos no General de Facção de {origin_city}.",
                f"5. 100% das vendas, transmutações e confecção de capas acontecem dentro de {origin_city}.",
                f"6. REGRA FISCAL DE TRANSMUTAÇÃO: O transmutador municipal SÓ converte Corações Sombrios (Caerleon) em corações da cidade natal. Não existe transmutação entre cidades reais (ex: Montanha -> Arbóreo). Portanto, corações de outras capitais reais devem ser vendidos no mercado local ou usados exclusivamente para capas da respectiva cidade (Fort Sterling / Morta-Viva)."
            ]
        },
        "recommended_cape": recommended_cape_dict,
        "cape_investment_audit": selected_cape_audit,
        "cape_investment_markdown": selected_cape_markdown,
        "ranked_strategies": ranked_list,
        "definitive_verdict": definitive_verdict,
        "branches": {
            "branch_1_external_rebuy": {
                "description": "Comprar novo fardo com prata do banco e estocar corações no baú",
                "cost_silver": cost_initial_pack,
                "can_afford": available_silver >= cost_initial_pack
            },
            "branch_2_perpetual_expansion": {
                "description": (
                    f"Transmutar todos em {origin_heart_info['name_pt']}"
                    if is_caerleon else
                    f"Ordem de venda paciente de {dest_heart_info['name_pt']}"
                ),
                "transmute_cost_silver": total_transmute_fee if is_caerleon else 0,
                "surplus_origin_hearts_stored": hearts_out if is_caerleon else 0,
                "net_profit_silver": transmute_net_profit if is_caerleon else patient_net_profit,
                "applicable": is_caerleon
            },
            "branch_3_hybrid_loop": {
                "description": (
                    "Transmutar os necessários para reiniciar e vender o excedente"
                    if is_caerleon else
                    "Vender corações recebidos e recomprar fardo no mercado local"
                ),
                "transmute_cost_silver": transmute_fee_next_trip if is_caerleon else 0,
                "surplus_hearts_sold": surplus_hearts_count,
                "immediate_net_silver_profit": net_cash_in_pocket,
                "silver_per_hour": cash_per_hour,
                "applicable": True
            },
            "branch_4_direct_sale": {
                "description": f"Liquidar todos os corações recebidos no Mercado de {origin_city}",
                "net_revenue_silver": net_direct_revenue,
                "net_profit_silver": direct_net_profit,
                "silver_per_hour": direct_silver_per_hour
            }
        }
    }



def validate_faction_inputs(
    current_city: str,
    available_silver: int,
    risk_profile: str,
    has_premium: bool,
    mount_type: str,
    session_mode: str,
    pack_size: int
) -> Dict[str, Any]:
    """
    Guardrail de Validação Prévia:
    Verifica a conformidade rigorosa dos 7 parâmetros obrigatórios da realidade do jogador antes de qualquer cálculo.
    NENHUM parâmetro é assumido silenciosamente por padrão.
    """
    errors = []

    if not current_city or not str(current_city).strip():
        errors.append("Cidade 'current_city' é obrigatória (ex: 'Lymhurst', 'Fort Sterling', 'Thetford', 'Martlock', 'Bridgewatch').")
        normalized_city = None
    else:
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
        errors.append("Saldo de prata 'available_silver' é obrigatório e deve ser um valor inteiro não-negativo.")

    valid_risks = ("SAFE_ONLY", "ALLOW_RED_ZONE")
    norm_risk = risk_profile.strip().upper() if risk_profile else ""
    if norm_risk not in valid_risks:
        errors.append(f"Perfil de risco 'risk_profile' é obrigatório. Use {valid_risks}.")

    valid_modes = ("CONTINUOUS_LOOP", "PATIENT_TRADER")
    norm_mode = session_mode.strip().upper() if session_mode else ""
    if norm_mode not in valid_modes:
        errors.append(f"Modo de sessão 'session_mode' é obrigatório. Use {valid_modes}.")

    if has_premium is None or not isinstance(has_premium, bool):
        errors.append("Status 'has_premium' é obrigatório (True ou False). O agente não pode presumir status fiscal sem confirmação.")

    if not mount_type or not str(mount_type).strip():
        errors.append("A montaria 'mount_type' é obrigatória (ex: 'T5_BOAR', 'T4_OX', 'T5_OX', 'T8_BEAR', etc.).")

    valid_pack_sizes = (3, 7, 15)
    if pack_size not in valid_pack_sizes:
        errors.append(f"Tamanho de fardo 'pack_size' é obrigatório e deve ser 3, 7 ou 15 corações (recebido: {pack_size}).")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "normalized_city": normalized_city,
        "normalized_risk": norm_risk,
        "normalized_mode": norm_mode,
        "has_premium": bool(has_premium) if has_premium is not None else False,
        "available_silver": int(available_silver) if available_silver is not None else 0,
        "mount_type": mount_type,
        "pack_size": pack_size
    }


def calculate_faction_transport_plan(
    current_city: str,
    available_silver: int,
    risk_profile: str,
    has_premium: bool,
    mount_type: str,
    session_mode: str,
    pack_size: int,
    target_destination: Optional[str] = None,
    mock_heart_prices: Optional[Dict[str, int]] = None,
    material_prices: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """
    Função Master de Execução do Motor 2:
    Valida guardrails da realidade do jogador, resolve compatibilidade física no Motor 1 e projeta lucros da rota.
    TODOS os parâmetros da realidade do jogador são estritamente obrigatórios.
    """
    # 1. Validação de Guardrails
    guard = validate_faction_inputs(
        current_city=current_city,
        available_silver=available_silver,
        risk_profile=risk_profile,
        has_premium=has_premium,
        mount_type=mount_type,
        session_mode=session_mode,
        pack_size=pack_size
    )
    if not guard["is_valid"]:
        return {
            "status": "GUARDRAIL_VALIDATION_FAILED",
            "message": "Faltam parâmetros obrigatórios da realidade do jogador ou foram passados com formato inválido.",
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
        # Tokens Oficiais
        "T1_FACTION_FOREST_TOKEN_1": 45000,
        "T1_FACTION_MOUNTAIN_TOKEN_1": 46000,
        "T1_FACTION_STEPPE_TOKEN_1": 44000,
        "T1_FACTION_SWAMP_TOKEN_1": 47000,
        "T1_FACTION_HIGHLAND_TOKEN_1": 43000,
        "T1_FACTION_CAERLEON_TOKEN_1": 62000,
        # IDs Legados
        "T4_HEART_WOOD": 45000,
        "T4_HEART_MOUNTAIN": 46000,
        "T4_HEART_BEAST": 44000,
        "T4_HEART_SWAMP": 47000,
        "T4_HEART_ROCK": 43000,
        "T4_HEART_UNDEAD": 62000,
        # Insumos de Manufatura de Capas
        "T4_CAPE": 3642,
        "T4_CAPEITEM_SMUGGLER_BP": 11976,
        "T4_RUNE": 8,
        "T4_SOUL": 82,
        "T4_CREST_FW_LYMHURST": 15000,
        "T4_CREST_FW_FORTSTERLING": 15000,
        "T4_CREST_FW_BRIDGEWATCH": 15000,
        "T4_CREST_FW_THETFORD": 15000,
        "T4_CREST_FW_MARTLOCK": 15000,
        "T4_CREST_FW_CAERLEON": 16000,
        "T4_CREST_HERETIC": 18000,
        "T4_CREST_UNDEAD": 22000,
        "T4_CREST_DEMON": 18000,
        "T4_CREST_MORGANA": 17000,
        "T4_CREST_KEEPER": 16000,
    }
    prices = material_prices or mock_heart_prices or default_prices

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

        target_cape_city = origin if dest.lower() == "caerleon" else dest
        cape_item_base = FACTION_CAPE_METADATA.get(target_cape_city, {}).get("item_id_base", "")
        cape_price_used = prices.get(f"T4_{cape_item_base}@2") or FACTION_CAPE_METADATA.get(target_cape_city, {}).get("default_price_t4_2", 175000)

        decision_tree = simulate_post_trip_decision_tree(
            origin_city=origin,
            destination_city=dest,
            pack_size=pack_size,
            origin_heart_price=origin_price,
            destination_heart_price=dest_price,
            available_silver=available_silver,
            has_premium=has_premium,
            session_mode=guard["normalized_mode"],
            cape_market_price=cape_price_used,
            trip_time_min=trip_time_min,
            material_prices=prices
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
        "where_to_sell": best_route["decision_tree"]["operational_protocol"]["where_to_sell"],
        "operational_protocol": best_route["decision_tree"]["operational_protocol"],
        "recommended_cape": best_route["decision_tree"]["recommended_cape"],
        "cape_investment_audit": best_route["decision_tree"].get("cape_investment_audit"),
        "cape_investment_markdown": best_route["decision_tree"].get("cape_investment_markdown"),
        "definitive_verdict": best_route["decision_tree"]["definitive_verdict"],
        "ranked_strategies": best_route["decision_tree"]["ranked_strategies"],
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

