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
