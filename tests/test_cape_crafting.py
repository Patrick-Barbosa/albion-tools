"""
Testes unitários para a Esteira de Manufatura de Capas de Facção (cape_crafting.py).
"""

try:
    import pytest
except ImportError:
    pytest = None
from src.albion_mcp.core.cape_crafting import (
    calculate_cape_crafting_cost,
    evaluate_cape_vs_raw_heart_profit,
    CAPE_RECIPES,
    FACTION_CAPE_IDS
)


def test_cape_recipes_structure():
    # T4 consome 1 coração
    assert CAPE_RECIPES[4]["hearts_consumed"] == 1
    # T6 consome 3 corações
    assert CAPE_RECIPES[6]["hearts_consumed"] == 3
    # T7 consome 5 corações
    assert CAPE_RECIPES[7]["hearts_consumed"] == 5
    # T8 consome 10 corações
    assert CAPE_RECIPES[8]["hearts_consumed"] == 10
    # Todos consomem 96 insumos por encantamento
    for t in (4, 5, 6, 7, 8):
        assert CAPE_RECIPES[t]["runes_per_enchant"] == 96


def test_cape_crafting_cost_calculation():
    # Capa T4.0 Normal Lymhurst
    cost_t4_0 = calculate_cape_crafting_cost(
        city_faction="Lymhurst",
        tier=4,
        enchantment=0,
        target_quality=1,
        heart_unit_cost=45000
    )
    assert cost_t4_0["hearts_consumed"] == 1
    assert cost_t4_0["tier"] == 4
    assert cost_t4_0["total_production_cost_silver"] > 45000

    # Capa T4.2 (deve incluir 96 runas e 96 almas)
    cost_t4_2 = calculate_cape_crafting_cost(
        city_faction="Lymhurst",
        tier=4,
        enchantment=2,
        target_quality=1,
        heart_unit_cost=45000
    )
    assert cost_t4_2["cost_breakdown"]["enchantment_total"] > 0
    assert len(cost_t4_2["cost_breakdown"]["enchantment_steps"]) == 2


def test_evaluate_cape_vs_raw_heart_profit():
    # Quando a capa vende por um preço alto no mercado (180k para T4.2)
    res_good = evaluate_cape_vs_raw_heart_profit(
        city_faction="Lymhurst",
        tier=4,
        enchantment=2,
        target_quality=1,
        heart_market_price=45000,
        cape_market_sell_price=180000,
        has_premium=True
    )
    assert res_good["is_cape_better"] is True
    assert res_good["recommendation"] == "CRAFT_AND_SELL_CAPE"
    assert res_good["delta_profit_per_heart"] > 0

    # Quando a capa vende por uma miséria (50k para T4.2 que custa mais de 70k para fazer)
    res_bad = evaluate_cape_vs_raw_heart_profit(
        city_faction="Lymhurst",
        tier=4,
        enchantment=2,
        target_quality=1,
        heart_market_price=45000,
        cape_market_sell_price=50000,
        has_premium=True
    )
    assert res_bad["is_cape_better"] is False
    assert res_bad["recommendation"] == "SELL_RAW_HEARTS"
    assert res_bad["delta_profit_per_heart"] < 0


def test_resolve_cape_metadata_all_types():
    from src.albion_mcp.core.cape_crafting import resolve_cape_metadata

    # Royal capes
    assert resolve_cape_metadata("Lymhurst")["cape_id"] == "CAPEITEM_FW_LYMHURST"
    assert resolve_cape_metadata("Caerleon")["cape_id"] == "CAPEITEM_FW_CAERLEON"
    assert resolve_cape_metadata("Fort Sterling")["cape_id"] == "CAPEITEM_FW_FORTSTERLING"

    # Mob and special capes
    assert resolve_cape_metadata("Capa de Contrabandista")["cape_id"] == "CAPEITEM_SMUGGLER"
    assert resolve_cape_metadata("smuggler")["cape_id"] == "CAPEITEM_SMUGGLER"
    assert resolve_cape_metadata("Capa Herege")["cape_id"] == "CAPEITEM_HERETIC"
    assert resolve_cape_metadata("heretic")["cape_id"] == "CAPEITEM_HERETIC"
    assert resolve_cape_metadata("Capa Morta-Viva")["cape_id"] == "CAPEITEM_UNDEAD"
    assert resolve_cape_metadata("undead")["cape_id"] == "CAPEITEM_UNDEAD"
    assert resolve_cape_metadata("Capa de Morgana")["cape_id"] == "CAPEITEM_MORGANA"
    assert resolve_cape_metadata("Capa Demoníaca")["cape_id"] == "CAPEITEM_DEMON"
    assert resolve_cape_metadata("Capa do Guardião")["cape_id"] == "CAPEITEM_KEEPER"


def test_get_eligible_capes_for_all_hearts():
    from src.albion_mcp.core.cape_crafting import get_eligible_capes_for_heart

    # Sombrio -> Caerleon + Contrabandista
    undead_capes = [c["cape_id"] for c in get_eligible_capes_for_heart("Coração Sombrio")]
    assert "CAPEITEM_FW_CAERLEON" in undead_capes
    assert "CAPEITEM_SMUGGLER" in undead_capes

    # Arbóreo -> Lymhurst + Herege
    wood_capes = [c["cape_id"] for c in get_eligible_capes_for_heart("Coração Arbóreo")]
    assert "CAPEITEM_FW_LYMHURST" in wood_capes
    assert "CAPEITEM_HERETIC" in wood_capes

    # Montanhoso -> Fort Sterling + Morta-Viva
    mountain_capes = [c["cape_id"] for c in get_eligible_capes_for_heart("Coração da Montanha")]
    assert "CAPEITEM_FW_FORTSTERLING" in mountain_capes
    assert "CAPEITEM_UNDEAD" in mountain_capes

    # Pântano -> Thetford + Morgana
    swamp_capes = [c["cape_id"] for c in get_eligible_capes_for_heart("Thetford")]
    assert "CAPEITEM_FW_THETFORD" in swamp_capes
    assert "CAPEITEM_MORGANA" in swamp_capes

    # Fera -> Bridgewatch + Demoníaca
    beast_capes = [c["cape_id"] for c in get_eligible_capes_for_heart("Bridgewatch")]
    assert "CAPEITEM_FW_BRIDGEWATCH" in beast_capes
    assert "CAPEITEM_DEMON" in beast_capes

    # Rocha -> Martlock + Guardião
    rock_capes = [c["cape_id"] for c in get_eligible_capes_for_heart("Martlock")]
    assert "CAPEITEM_FW_MARTLOCK" in rock_capes
    assert "CAPEITEM_KEEPER" in rock_capes


def test_optimize_cape_crafting_for_heart():
    from src.albion_mcp.core.cape_crafting import optimize_cape_crafting_for_heart

    # Coração Sombrio: Contrabandista (240k) vs Caerleon (175k)
    res_caerleon = optimize_cape_crafting_for_heart(
        heart_or_city="Coração Sombrio",
        tier=4,
        enchantment=2,
        target_quality=1,
        heart_market_price=62000,
        has_premium=True
    )
    assert res_caerleon["best_cape_name"] == "Capa de Contrabandista"
    assert res_caerleon["delta_silver_advantage"] > 0
    assert len(res_caerleon["ranked_capes"]) == 2
    assert "superando a Capa de Caerleon" in res_caerleon["verdict"]

    # Coração da Montanha: Morta-Viva (260k) vs Fort Sterling (160k)
    res_fs = optimize_cape_crafting_for_heart(
        heart_or_city="Fort Sterling",
        tier=4,
        enchantment=2,
        target_quality=1,
        heart_market_price=46000,
        has_premium=True
    )
    assert res_fs["best_cape_name"] == "Capa Morta-Viva"
    assert res_fs["delta_silver_advantage"] > 0
    assert len(res_fs["ranked_capes"]) == 2
    assert "superando a Capa de Fort Sterling" in res_fs["verdict"]

