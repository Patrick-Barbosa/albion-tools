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

# Identificadores de itens de Capas de Facção por cidade
FACTION_CAPE_IDS = {
    "Lymhurst": "CAPEITEM_FW_LYMHURST",
    "Fort Sterling": "CAPEITEM_FW_FORTSTERLING",
    "Bridgewatch": "CAPEITEM_FW_BRIDGEWATCH",
    "Thetford": "CAPEITEM_FW_THETFORD",
    "Martlock": "CAPEITEM_FW_MARTLOCK",
    "Caerleon": "CAPEITEM_FW_CAERLEON"
}


def calculate_cape_crafting_cost(
    city_faction: str,
    tier: int,
    enchantment: int = 0,
    target_quality: int = 1,
    heart_unit_cost: int = 45000,
    custom_prices: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """
    Calcula o custo completo de confecção, encantamento e reroll de uma Capa de Facção.

    Parâmetros:
    - city_faction: Cidade da facção ('Lymhurst', 'Caerleon', etc.)
    - tier: Tier da capa (4 a 8)
    - enchantment: Nível de encantamento (0 a 3)
    - target_quality: 1 (Normal), 2 (Bom), 3 (Notável), 4 (Excelente), 5 (Obra-prima)
    - heart_unit_cost: Custo unitário em prata do coração da facção
    - custom_prices: Dicionário opcional de preços de insumos de mercado
    """
    if tier not in CAPE_RECIPES:
        raise ValueError(f"Tier de capa inválido: {tier}. Use de 4 a 8.")
    if city_faction not in FACTION_CAPE_IDS:
        raise ValueError(f"Facção inválida: {city_faction}. Use {list(FACTION_CAPE_IDS.keys())}.")
    if enchantment not in (0, 1, 2, 3):
        raise ValueError("Encantamento deve ser 0 (.0), 1 (.1), 2 (.2) ou 3 (.3).")

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
        "city_faction": city_faction,
        "cape_full_id": f"T{tier}_{FACTION_CAPE_IDS[city_faction]}" + (f"@{enchantment}" if enchantment > 0 else ""),
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
    Compara a rentabilidade de confeccionar e vender a Capa de Facção
    contra a venda bruta dos corações sem esforço de produção.
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
    # (Receita da capa - custos de outros insumos) / corações
    net_value_per_heart_used = int((net_cape_revenue - non_heart_cost) / hearts_consumed) if hearts_consumed > 0 else 0

    # Lucro da venda bruta direta do coração no mercado
    net_raw_heart_sale = int(heart_market_price * (1.0 - tax_rate))
    delta_per_heart = net_value_per_heart_used - net_raw_heart_sale

    is_cape_better = (delta_per_heart > 0)

    if is_cape_better:
        recommendation = "CRAFT_AND_SELL_CAPE"
        verdict = (
            f"Confeccionar a Capa T{tier}.{enchantment} agrega +{delta_per_heart:,} ⚗ de lucro "
            f"por coração consumido acima da venda do coração cru no mercado."
        )
    else:
        recommendation = "SELL_RAW_HEARTS"
        verdict = (
            f"Vender os corações brutos é mais rentável (ou menos arriscado). "
            f"A confecção da capa deixaria {abs(delta_per_heart):,} ⚗ a menos por coração."
        )

    return {
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
        "roi_pct": round((net_profit_cape / craft_data["total_production_cost_silver"]) * 100, 1)
    }
