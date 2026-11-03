"""
Motor de Manufatura de Capas de Facção (Cape Crafting & Downstream Value Engine).

Calcula os custos de confecção de Capas de Facção (T4..T8), custo de encantamento
na Artifact Foundry (múltiplos de 96 runas/almas/relíquias), valor esperado de reroll
de qualidade na Repair Station e o ganho líquido por coração investido vs venda direta.
"""

from typing import Dict, Any, List, Optional

# Receitas base de Capas de Facção (consumo de corações por tier)
CAPE_RECIPES = {
    4: {
        "tier": 4,
        "regular_cape_id": "T4_CAPE",
        "crest_id_suffix": "T4_FACTION_CREST",
        "hearts_consumed": 1,
        "base_item_value": 192,
        "runes_per_enchant": 96
    },
    5: {
        "tier": 5,
        "regular_cape_id": "T5_CAPE",
        "crest_id_suffix": "T5_FACTION_CREST",
        "hearts_consumed": 1,
        "base_item_value": 384,
        "runes_per_enchant": 96
    },
    6: {
        "tier": 6,
        "regular_cape_id": "T6_CAPE",
        "crest_id_suffix": "T6_FACTION_CREST",
        "hearts_consumed": 3,
        "base_item_value": 768,
        "runes_per_enchant": 96
    },
    7: {
        "tier": 7,
        "regular_cape_id": "T7_CAPE",
        "crest_id_suffix": "T7_FACTION_CREST",
        "hearts_consumed": 5,
        "base_item_value": 1536,
        "runes_per_enchant": 96
    },
    8: {
        "tier": 8,
        "regular_cape_id": "T8_CAPE",
        "crest_id_suffix": "T8_FACTION_CREST",
        "hearts_consumed": 10,
        "base_item_value": 3072,
        "runes_per_enchant": 96
    }
}

from .calculator import calculate_quality_reroll_ev
from .metadata import QUALITY_NAMES

# Mapeamento completo de todos os tipos de Capas por Coração de Recurso no Albion Online
ALL_CAPES_CATALOG: Dict[str, Dict[str, Any]] = {
    # ── Coração Sombrio (T1_FACTION_CAERLEON_TOKEN_1 / Caerleon) ─────
    "CAPEITEM_FW_CAERLEON": {
        "cape_id": "CAPEITEM_FW_CAERLEON",
        "name_pt": "Capa de Caerleon",
        "name_en": "Caerleon Cape",
        "category": "ROYAL_FACTION",
        "heart_id": "T1_FACTION_CAERLEON_TOKEN_1",
        "legacy_heart_id": "T4_HEART_UNDEAD",
        "heart_name_pt": "Coração Sombrio",
        "crest_prefix": "CREST_FW_CAERLEON",
        "city": "Caerleon",
        "default_price_t4_2": 175000,
        "description": "Reinicia o tempo de recarga da habilidade Q."
    },
    "CAPEITEM_SMUGGLER": {
        "cape_id": "CAPEITEM_SMUGGLER",
        "name_pt": "Capa de Contrabandista",
        "name_en": "Smuggler Cape",
        "category": "SPECIAL_OUTLAW",
        "heart_id": "T1_FACTION_CAERLEON_TOKEN_1",
        "legacy_heart_id": "T4_HEART_UNDEAD",
        "heart_name_pt": "Coração Sombrio",
        "crest_prefix": "CAPEITEM_SMUGGLER_BP",
        "city": "Caerleon",
        "default_price_t4_2": 240000,
        "description": "Reduz o cooldown da poção em 90s ao usar consumível (Altíssima demanda PvP)."
    },

    # ── Coração Arbóreo (T1_FACTION_FOREST_TOKEN_1 / Lymhurst) ────────
    "CAPEITEM_FW_LYMHURST": {
        "cape_id": "CAPEITEM_FW_LYMHURST",
        "name_pt": "Capa de Lymhurst",
        "name_en": "Lymhurst Cape",
        "category": "ROYAL_FACTION",
        "heart_id": "T1_FACTION_FOREST_TOKEN_1",
        "legacy_heart_id": "T4_HEART_WOOD",
        "heart_name_pt": "Coração Arbóreo",
        "crest_prefix": "CREST_FW_LYMHURST",
        "city": "Lymhurst",
        "default_price_t4_2": 175000,
        "description": "Restaura mana quando a energia cai abaixo de 40%."
    },
    "CAPEITEM_HERETIC": {
        "cape_id": "CAPEITEM_HERETIC",
        "name_pt": "Capa Herege",
        "name_en": "Heretic Cape",
        "category": "MOB_FACTION",
        "heart_id": "T1_FACTION_FOREST_TOKEN_1",
        "legacy_heart_id": "T4_HEART_WOOD",
        "heart_name_pt": "Coração Arbóreo",
        "crest_prefix": "CREST_HERETIC",
        "city": "Lymhurst",
        "default_price_t4_2": 185000,
        "description": "Cria armadilha enraizadora ao usar habilidade de bota."
    },

    # ── Coração da Montanha (T1_FACTION_MOUNTAIN_TOKEN_1 / Fort Sterling)
    "CAPEITEM_FW_FORTSTERLING": {
        "cape_id": "CAPEITEM_FW_FORTSTERLING",
        "name_pt": "Capa de Fort Sterling",
        "name_en": "Fort Sterling Cape",
        "category": "ROYAL_FACTION",
        "heart_id": "T1_FACTION_MOUNTAIN_TOKEN_1",
        "legacy_heart_id": "T4_HEART_MOUNTAIN",
        "heart_name_pt": "Coração da Montanha",
        "crest_prefix": "CREST_FW_FORTSTERLING",
        "city": "Fort Sterling",
        "default_price_t4_2": 160000,
        "description": "Remove e imuniza contra efeitos de controle de grupo (CC cleanse)."
    },
    "CAPEITEM_UNDEAD": {
        "cape_id": "CAPEITEM_UNDEAD",
        "name_pt": "Capa Morta-Viva",
        "name_en": "Undead Cape",
        "category": "MOB_FACTION",
        "heart_id": "T1_FACTION_MOUNTAIN_TOKEN_1",
        "legacy_heart_id": "T4_HEART_MOUNTAIN",
        "heart_name_pt": "Coração da Montanha",
        "crest_prefix": "CREST_UNDEAD",
        "city": "Fort Sterling",
        "default_price_t4_2": 260000,
        "description": "Concede invisibilidade automática ao atingir vida crítica (<25%). Grande valor de mercado."
    },

    # ── Coração do Pântano (T1_FACTION_SWAMP_TOKEN_1 / Thetford) ────
    "CAPEITEM_FW_THETFORD": {
        "cape_id": "CAPEITEM_FW_THETFORD",
        "name_pt": "Capa de Thetford",
        "name_en": "Thetford Cape",
        "category": "ROYAL_FACTION",
        "heart_id": "T1_FACTION_SWAMP_TOKEN_1",
        "legacy_heart_id": "T4_HEART_SWAMP",
        "heart_name_pt": "Coração do Pântano",
        "crest_prefix": "CREST_FW_THETFORD",
        "city": "Thetford",
        "default_price_t4_2": 170000,
        "description": "Dispara corrente de raio que atinge até 4 inimigos (Alto dano PvE/PvP)."
    },
    "CAPEITEM_MORGANA": {
        "cape_id": "CAPEITEM_MORGANA",
        "name_pt": "Capa de Morgana",
        "name_en": "Morgana Cape",
        "category": "MOB_FACTION",
        "heart_id": "T1_FACTION_SWAMP_TOKEN_1",
        "legacy_heart_id": "T4_HEART_SWAMP",
        "heart_name_pt": "Coração do Pântano",
        "crest_prefix": "CREST_MORGANA",
        "city": "Thetford",
        "default_price_t4_2": 180000,
        "description": "Aumenta drasticamente a velocidade de conjuração e ataque ao usar E."
    },

    # ── Coração de Pedra / Fera (T1_FACTION_STEPPE_TOKEN_1 / Bridgewatch)
    "CAPEITEM_FW_BRIDGEWATCH": {
        "cape_id": "CAPEITEM_FW_BRIDGEWATCH",
        "name_pt": "Capa de Bridgewatch",
        "name_en": "Bridgewatch Cape",
        "category": "ROYAL_FACTION",
        "heart_id": "T1_FACTION_STEPPE_TOKEN_1",
        "legacy_heart_id": "T4_HEART_BEAST",
        "heart_name_pt": "Coração de Bridgewatch",
        "crest_prefix": "CREST_FW_BRIDGEWATCH",
        "city": "Bridgewatch",
        "default_price_t4_2": 165000,
        "description": "Evoca tempestade de areia que reduz dano e velocidade de ataque dos inimigos."
    },
    "CAPEITEM_DEMON": {
        "cape_id": "CAPEITEM_DEMON",
        "name_pt": "Capa Demoníaca",
        "name_en": "Demon Cape",
        "category": "MOB_FACTION",
        "heart_id": "T1_FACTION_STEPPE_TOKEN_1",
        "legacy_heart_id": "T4_HEART_BEAST",
        "heart_name_pt": "Coração de Bridgewatch",
        "crest_prefix": "CREST_DEMON",
        "city": "Bridgewatch",
        "default_price_t4_2": 195000,
        "description": "Cria poça de lava incandescente que causa dano contínuo devastador."
    },

    # ── Coração de Fera / Rocha (T1_FACTION_HIGHLAND_TOKEN_1 / Martlock)
    "CAPEITEM_FW_MARTLOCK": {
        "cape_id": "CAPEITEM_FW_MARTLOCK",
        "name_pt": "Capa de Martlock",
        "name_en": "Martlock Cape",
        "category": "ROYAL_FACTION",
        "heart_id": "T1_FACTION_HIGHLAND_TOKEN_1",
        "legacy_heart_id": "T4_HEART_ROCK",
        "heart_name_pt": "Coração de Martlock",
        "crest_prefix": "CREST_FW_MARTLOCK",
        "city": "Martlock",
        "default_price_t4_2": 160000,
        "description": "Concede escudo invulnerável temporário contra dano ao sofrer ataque em vida baixa."
    },
    "CAPEITEM_KEEPER": {
        "cape_id": "CAPEITEM_KEEPER",
        "name_pt": "Capa do Guardião",
        "name_en": "Keeper Cape",
        "category": "MOB_FACTION",
        "heart_id": "T1_FACTION_HIGHLAND_TOKEN_1",
        "legacy_heart_id": "T4_HEART_ROCK",
        "heart_name_pt": "Coração de Martlock",
        "crest_prefix": "CREST_KEEPER",
        "city": "Martlock",
        "default_price_t4_2": 175000,
        "description": "Concede bônus massivo de dano e cura ao receber dano abaixo de certo limiar."
    }
}

# Compatibilidade reversa com mapeamento municipal
FACTION_CAPE_IDS = {
    "Lymhurst": "CAPEITEM_FW_LYMHURST",
    "Fort Sterling": "CAPEITEM_FW_FORTSTERLING",
    "Bridgewatch": "CAPEITEM_FW_BRIDGEWATCH",
    "Thetford": "CAPEITEM_FW_THETFORD",
    "Martlock": "CAPEITEM_FW_MARTLOCK",
    "Caerleon": "CAPEITEM_FW_CAERLEON"
}


def resolve_cape_metadata(identifier: str) -> Dict[str, Any]:
    """
    Resolve qualquer identificador de capa para o metadado completo.
    Suporta ID do item, nome da cidade, nome em PT-BR ou EN-US.
    """
    norm = identifier.strip().lower()
    # 1. Chave exata ou cape_id
    for k, v in ALL_CAPES_CATALOG.items():
        if k.lower() == norm or v["cape_id"].lower() == norm:
            return v

    # 2. Cidade natal de facção real
    for k, v in ALL_CAPES_CATALOG.items():
        if v["category"] == "ROYAL_FACTION" and v["city"].lower() == norm:
            return v

    # 3. Apelidos e nomes parciais
    aliases = {
        "contrabandista": "CAPEITEM_SMUGGLER",
        "smuggler": "CAPEITEM_SMUGGLER",
        "herege": "CAPEITEM_HERETIC",
        "heretico": "CAPEITEM_HERETIC",
        "heretic": "CAPEITEM_HERETIC",
        "morta-viva": "CAPEITEM_UNDEAD",
        "morta viva": "CAPEITEM_UNDEAD",
        "morto-vivo": "CAPEITEM_UNDEAD",
        "morto vivo": "CAPEITEM_UNDEAD",
        "undead": "CAPEITEM_UNDEAD",
        "morgana": "CAPEITEM_MORGANA",
        "demoniaca": "CAPEITEM_DEMON",
        "demoníaca": "CAPEITEM_DEMON",
        "demonio": "CAPEITEM_DEMON",
        "demônio": "CAPEITEM_DEMON",
        "demon": "CAPEITEM_DEMON",
        "guardiao": "CAPEITEM_KEEPER",
        "guardião": "CAPEITEM_KEEPER",
        "keeper": "CAPEITEM_KEEPER",
    }
    for alias, cape_key in aliases.items():
        if alias in norm:
            return ALL_CAPES_CATALOG[cape_key]

    for k, v in ALL_CAPES_CATALOG.items():
        if v["name_pt"].lower() in norm or norm in v["name_pt"].lower() or v["name_en"].lower() in norm:
            return v

    valid_names = [v["name_pt"] for v in ALL_CAPES_CATALOG.values()]
    raise ValueError(f"Capa ou facção inválida: '{identifier}'. Opções válidas: {valid_names}.")


def get_eligible_capes_for_heart(heart_or_city: str) -> List[Dict[str, Any]]:
    """
    Retorna a lista de todas as capas que podem ser fabricadas a partir de um coração ou cidade.
    Ex: Coração Sombrio -> [Capa de Caerleon, Capa de Contrabandista]
        Coração Arbóreo -> [Capa de Lymhurst, Capa Herege]
        Coração da Montanha -> [Capa de Fort Sterling, Capa Morta-Viva]
    """
    norm = heart_or_city.strip().lower()
    heart_map = {
        "caerleon": "T1_FACTION_CAERLEON_TOKEN_1",
        "sombrio": "T1_FACTION_CAERLEON_TOKEN_1",
        "shadowheart": "T1_FACTION_CAERLEON_TOKEN_1",
        "undead": "T1_FACTION_CAERLEON_TOKEN_1",
        "t4_heart_undead": "T1_FACTION_CAERLEON_TOKEN_1",
        "t1_faction_caerleon_token_1": "T1_FACTION_CAERLEON_TOKEN_1",

        "lymhurst": "T1_FACTION_FOREST_TOKEN_1",
        "arboreo": "T1_FACTION_FOREST_TOKEN_1",
        "arbóreo": "T1_FACTION_FOREST_TOKEN_1",
        "arvore": "T1_FACTION_FOREST_TOKEN_1",
        "árvore": "T1_FACTION_FOREST_TOKEN_1",
        "treeheart": "T1_FACTION_FOREST_TOKEN_1",
        "t4_heart_wood": "T1_FACTION_FOREST_TOKEN_1",
        "t1_faction_forest_token_1": "T1_FACTION_FOREST_TOKEN_1",

        "fort sterling": "T1_FACTION_MOUNTAIN_TOKEN_1",
        "montanha": "T1_FACTION_MOUNTAIN_TOKEN_1",
        "montanhoso": "T1_FACTION_MOUNTAIN_TOKEN_1",
        "mountainheart": "T1_FACTION_MOUNTAIN_TOKEN_1",
        "t4_heart_mountain": "T1_FACTION_MOUNTAIN_TOKEN_1",
        "t1_faction_mountain_token_1": "T1_FACTION_MOUNTAIN_TOKEN_1",

        "thetford": "T1_FACTION_SWAMP_TOKEN_1",
        "pantano": "T1_FACTION_SWAMP_TOKEN_1",
        "pântano": "T1_FACTION_SWAMP_TOKEN_1",
        "vineheart": "T1_FACTION_SWAMP_TOKEN_1",
        "swampheart": "T1_FACTION_SWAMP_TOKEN_1",
        "t4_heart_swamp": "T1_FACTION_SWAMP_TOKEN_1",
        "t1_faction_swamp_token_1": "T1_FACTION_SWAMP_TOKEN_1",

        "bridgewatch": "T1_FACTION_STEPPE_TOKEN_1",
        "estepes": "T1_FACTION_STEPPE_TOKEN_1",
        "beastheart": "T1_FACTION_STEPPE_TOKEN_1",
        "t4_heart_beast": "T1_FACTION_STEPPE_TOKEN_1",
        "t1_faction_steppe_token_1": "T1_FACTION_STEPPE_TOKEN_1",

        "martlock": "T1_FACTION_HIGHLAND_TOKEN_1",
        "rocha": "T1_FACTION_HIGHLAND_TOKEN_1",
        "pedra": "T1_FACTION_HIGHLAND_TOKEN_1",
        "rockheart": "T1_FACTION_HIGHLAND_TOKEN_1",
        "t4_heart_rock": "T1_FACTION_HIGHLAND_TOKEN_1",
        "t1_faction_highland_token_1": "T1_FACTION_HIGHLAND_TOKEN_1"
    }
    target_hid = None
    for k, hid in heart_map.items():
        if k in norm:
            target_hid = hid
            break
    if not target_hid:
        target_hid = "T1_FACTION_FOREST_TOKEN_1"

    return [c for c in ALL_CAPES_CATALOG.values() if c["heart_id"] == target_hid or c.get("legacy_heart_id") == target_hid]


def calculate_cape_crafting_cost(
    city_faction: str,
    tier: int,
    enchantment: int = 0,
    target_quality: int = 1,
    heart_unit_cost: int = 45000,
    custom_prices: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """
    Calcula o custo completo de confecção, encantamento e reroll de uma Capa.
    Suporta todas as Capas Reais e Especiais (Heretic, Undead, Smuggler, Morgana, Demon, Keeper).

    Parâmetros:
    - city_faction: Nome da cidade ou identificador da capa ('Lymhurst', 'CAPEITEM_SMUGGLER', 'Capa Morta-Viva', etc.)
    - tier: Tier da capa (4 a 8)
    - enchantment: Nível de encantamento (0 a 3)
    - target_quality: 1 (Normal), 2 (Bom), 3 (Notável), 4 (Excelente), 5 (Obra-prima)
    - heart_unit_cost: Custo unitário em prata do coração correspondente
    - custom_prices: Dicionário opcional de preços de insumos de mercado
    """
    if tier not in CAPE_RECIPES:
        raise ValueError(f"Tier de capa inválido: {tier}. Use de 4 a 8.")
    if enchantment not in (0, 1, 2, 3):
        raise ValueError("Encantamento deve ser 0 (.0), 1 (.1), 2 (.2) ou 3 (.3).")

    cape_meta = resolve_cape_metadata(city_faction)
    recipe = CAPE_RECIPES[tier]
    prices = custom_prices or {}

    # Preços de mercado estimados de referência
    default_cape_base_price = {4: 8000, 5: 22000, 6: 60000, 7: 150000, 8: 400000}
    default_crest_price = {4: 15000, 5: 35000, 6: 90000, 7: 220000, 8: 600000}
    default_enchant_mat_price = {
        4: {"rune": 25, "soul": 120, "relic": 600},
        5: {"rune": 70, "soul": 350, "relic": 1800},
        6: {"rune": 200, "soul": 1100, "relic": 4500},
        7: {"rune": 650, "soul": 3200, "relic": 12000},
        8: {"rune": 2200, "soul": 9500, "relic": 35000},
    }

    cape_base_cost = prices.get(f"T{tier}_CAPE", default_cape_base_price[tier])
    crest_cost = prices.get(f"T{tier}_CREST", default_crest_price[tier])
    hearts_needed = recipe["hearts_consumed"]
    total_heart_cost = hearts_needed * heart_unit_cost

    # Custo de Crafting Flat (.0)
    flat_craft_cost = cape_base_cost + crest_cost + total_heart_cost

    # Custo de Encantamento (96 insumos por nível)
    enchant_cost = 0
    enchant_details = []
    mat_tier_prices = default_enchant_mat_price[tier]

    if enchantment >= 1:
        rune_cost = prices.get(f"T{tier}_RUNE", mat_tier_prices["rune"]) * 96
        enchant_cost += rune_cost
        enchant_details.append({"level": 1, "material": f"96x Runa T{tier}", "cost": rune_cost})
    if enchantment >= 2:
        soul_cost = prices.get(f"T{tier}_SOUL", mat_tier_prices["soul"]) * 96
        enchant_cost += soul_cost
        enchant_details.append({"level": 2, "material": f"96x Alma T{tier}", "cost": soul_cost})
    if enchantment >= 3:
        relic_cost = prices.get(f"T{tier}_RELIC", mat_tier_prices["relic"]) * 96
        enchant_cost += relic_cost
        enchant_details.append({"level": 3, "material": f"96x Relíquia T{tier}", "cost": relic_cost})

    # Custo de Reroll de Qualidade na Repair Station (centralizado via calculator)
    expected_reroll_cost = 0
    expected_attempts = 1.0
    if target_quality > 1:
        reroll_ev = calculate_quality_reroll_ev(
            tier=tier,
            slot_type="CAPE",
            current_quality=1,
            target_quality=target_quality
        )
        expected_reroll_cost = reroll_ev["expected_total_cost_silver"]
        expected_attempts = reroll_ev["total_expected_attempts"]

    total_production_cost = flat_craft_cost + enchant_cost + expected_reroll_cost

    return {
        "city_faction": cape_meta["city"],
        "cape_id": cape_meta["cape_id"],
        "cape_name_pt": cape_meta["name_pt"],
        "cape_name_en": cape_meta["name_en"],
        "cape_category": cape_meta["category"],
        "cape_full_id": f"T{tier}_{cape_meta['cape_id']}" + (f"@{enchantment}" if enchantment > 0 else ""),
        "tier": tier,
        "enchantment": enchantment,
        "target_quality": QUALITY_NAMES.get(target_quality, "Normal"),
        "hearts_consumed": hearts_needed,
        "cost_breakdown": {
            "regular_cape_cost": cape_base_cost,
            "crest_cost": crest_cost,
            "hearts_cost": total_heart_cost,
            "flat_craft_total": flat_craft_cost,
            "enchantment_total": enchant_cost,
            "enchantment_steps": enchant_details,
            "expected_reroll_cost": expected_reroll_cost,
            "reroll_attempts_expected": expected_attempts
        },
        "total_production_cost_silver": total_production_cost
    }


def evaluate_cape_vs_raw_heart_profit(
    city_faction: str,
    tier: int,
    enchantment: int = 0,
    target_quality: int = 1,
    heart_market_price: int = 45000,
    cape_market_sell_price: int = 120000,
    has_premium: bool = True
) -> Dict[str, Any]:
    """
    Compara a rentabilidade de confeccionar e vender uma Capa específica
    (Real, Mob ou Especial) contra a venda bruta dos corações.
    """
    craft_data = calculate_cape_crafting_cost(
        city_faction=city_faction,
        tier=tier,
        enchantment=enchantment,
        target_quality=target_quality,
        heart_unit_cost=heart_market_price
    )

    tax_rate = 0.04 if has_premium else 0.08
    net_cape_revenue = int(cape_market_sell_price * (1.0 - tax_rate - 0.025))  # Deduz 2.5% de setup fee
    hearts_consumed = craft_data["hearts_consumed"]

    # Custo de insumos sem o coração (Capa + Brasão + Encanto + Reroll)
    non_heart_cost = (
        craft_data["cost_breakdown"]["regular_cape_cost"]
        + craft_data["cost_breakdown"]["crest_cost"]
        + craft_data["cost_breakdown"]["enchantment_total"]
        + craft_data["cost_breakdown"]["expected_reroll_cost"]
    )

    # Lucro líquido absoluto da operação de capa
    net_profit_cape = net_cape_revenue - craft_data["total_production_cost_silver"]

    # Valor gerado por cada coração consumido na confecção da capa
    net_value_per_heart_used = int((net_cape_revenue - non_heart_cost) / hearts_consumed) if hearts_consumed > 0 else 0

    # Lucro da venda bruta direta do coração no mercado
    net_raw_heart_sale = int(heart_market_price * (1.0 - tax_rate))
    delta_per_heart = net_value_per_heart_used - net_raw_heart_sale

    is_cape_better = (delta_per_heart > 0)
    cape_name = craft_data["cape_name_pt"]

    if is_cape_better:
        recommendation = "CRAFT_AND_SELL_CAPE"
        verdict = (
            f"Confeccionar {cape_name} T{tier}.{enchantment} agrega +{delta_per_heart:,} 🪙 de lucro "
            f"por coração consumido acima da venda do coração cru no mercado."
        ).replace(",", ".")
    else:
        recommendation = "SELL_RAW_HEARTS"
        verdict = (
            f"Vender os corações brutos é mais rentável do que fazer {cape_name}. "
            f"A confecção deixaria {abs(delta_per_heart):,} 🪙 a menos por coração."
        ).replace(",", ".")

    return {
        "cape_id": craft_data["cape_id"],
        "cape_name_pt": cape_name,
        "cape_category": craft_data["cape_category"],
        "recommendation": recommendation,
        "is_cape_better": is_cape_better,
        "verdict": verdict,
        "tier": tier,
        "enchantment": enchantment,
        "target_quality": craft_data["target_quality"],
        "hearts_consumed": hearts_consumed,
        "net_cape_sale_revenue": net_cape_revenue,
        "total_production_cost": craft_data["total_production_cost_silver"],
        "net_profit_cape": net_profit_cape,
        "net_value_per_heart_in_cape": net_value_per_heart_used,
        "net_raw_heart_sale_benchmark": net_raw_heart_sale,
        "delta_profit_per_heart": delta_per_heart,
        "roi_pct": round((net_profit_cape / craft_data["total_production_cost_silver"]) * 100, 1) if craft_data["total_production_cost_silver"] > 0 else 0.0
    }


def optimize_cape_crafting_for_heart(
    heart_or_city: str,
    tier: int = 4,
    enchantment: int = 2,
    target_quality: int = 1,
    heart_market_price: int = 45000,
    custom_cape_prices: Optional[Dict[str, int]] = None,
    has_premium: bool = True
) -> Dict[str, Any]:
    """
    Analisa TODAS as capas que consomem determinado coração (ex: Lymhurst vs Herege,
    Fort Sterling vs Morta-Viva, Caerleon vs Contrabandista) e determina a opção de lucro máximo.
    """
    eligible = get_eligible_capes_for_heart(heart_or_city)
    custom_prices = custom_cape_prices or {}

    evaluated = []
    for cape_info in eligible:
        cape_key = cape_info["cape_id"]
        sell_p = (
            custom_prices.get(cape_key)
            or custom_prices.get(cape_info["name_pt"])
            or cape_info["default_price_t4_2"]
        )

        analysis = evaluate_cape_vs_raw_heart_profit(
            city_faction=cape_key,
            tier=tier,
            enchantment=enchantment,
            target_quality=target_quality,
            heart_market_price=heart_market_price,
            cape_market_sell_price=sell_p,
            has_premium=has_premium
        )
        analysis["market_sell_price_used"] = sell_p
        analysis["description"] = cape_info["description"]
        evaluated.append(analysis)

    evaluated.sort(key=lambda x: x["net_profit_cape"], reverse=True)
    best = evaluated[0]
    runner_up = evaluated[1] if len(evaluated) > 1 else None

    delta_adv = (best["net_profit_cape"] - runner_up["net_profit_cape"]) if runner_up else 0

    def _fmt(val: float) -> str:
        return f"{int(val):,}".replace(",", ".")

    if runner_up and delta_adv > 0:
        verdict = (
            f"👉 OTIMIZAÇÃO DE CAPA: Confeccionar a {best['cape_name_pt']} T{tier}.{enchantment} é a mais lucrativa! "
            f"Ela gera {_fmt(best['net_profit_cape'])} 🪙 de lucro limpo ({_fmt(best['delta_profit_per_heart'])} 🪙 acima do coração bruto), "
            f"superando a {runner_up['cape_name_pt']} em +{_fmt(delta_adv)} 🪙 de lucro líquido por capa."
        )
    else:
        verdict = (
            f"👉 OTIMIZAÇÃO DE CAPA: A melhor opção para este coração é a {best['cape_name_pt']} T{tier}.{enchantment}, "
            f"gerando {_fmt(best['net_profit_cape'])} 🪙 de lucro líquido ({_fmt(best['delta_profit_per_heart'])} 🪙 de ganho por coração)."
        )

    return {
        "heart_evaluated": heart_or_city,
        "tier": tier,
        "enchantment": enchantment,
        "best_cape_name": best["cape_name_pt"],
        "best_cape_id": best["cape_id"],
        "best_cape_profit": best["net_profit_cape"],
        "delta_silver_advantage": delta_adv,
        "verdict": verdict,
        "ranked_capes": evaluated
    }
