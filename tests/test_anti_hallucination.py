"""
Testes unitários rigorosos para as ferramentas determinísticas Anti-Alucinação.
"""

import pytest
from src.albion_mcp.tools.anti_hallucination import (
    albion_calculate_breakeven_price,
    albion_audit_quote_freshness_and_phantom,
    albion_allocate_portfolio_budget,
    albion_simulate_quality_reroll,
    albion_calculate_exact_loadout_capacity,
    albion_calculate_transmutation_cost,
)


def test_calculate_breakeven_price():
    # Compra por 100.000 via buy order (+2.5% = 102.500)
    # Com Premium: imposto = 4.0%, setup = 2.5% => net_factor = 0.935
    # Preço mínimo de venda para 0% ROI: ceil(102500 / 0.935) = 109626
    be = albion_calculate_breakeven_price(
        buy_price=100000,
        is_buy_order=True,
        has_premium=True,
        price_updates_buy=0,
        price_updates_sell=0,
        target_roi_pct=0.0
    )
    assert be["effective_cost"] == 102500
    assert be["min_sell_order_price"] == 109626

    # Testando se vendendo no min_sell_order_price o lucro líquido é não-negativo
    sell_net = int(round(be["min_sell_order_price"] * (1 - 0.04 - 0.025)))
    assert sell_net >= be["effective_cost"]

    # Testando com meta de 20% ROI
    be_20 = albion_calculate_breakeven_price(
        buy_price=100000,
        is_buy_order=True,
        has_premium=True,
        target_roi_pct=20.0
    )
    assert be_20["min_sell_order_price"] > be["min_sell_order_price"]
    assert be_20["target_net_revenue"] == 123000


def test_audit_quote_freshness_and_phantom():
    # Preço normal
    audit_normal = albion_audit_quote_freshness_and_phantom(
        item_id="T4_BAG",
        city="Lymhurst",
        quote_price=4500,
        quote_type="sell_order",
        age_seconds=45
    )
    assert audit_normal["freshness"]["status"] == "LIVE_CONFIRMED"
    assert "safe_max_bid_silver" in audit_normal["safe_guardrails"]

    # Preço absurdamente alto (+100% sobre histórico)
    audit_phantom = albion_audit_quote_freshness_and_phantom(
        item_id="T4_BAG",
        city="Lymhurst",
        quote_price=250000,  # 250k numa bolsa T4!
        quote_type="sell_order",
        age_seconds=1200
    )
    assert audit_phantom["phantom_audit"]["status"] == "PHANTOM_SUSPECT"
    assert audit_phantom["freshness"]["status"] == "STALE_WARNING"
    assert audit_phantom["phantom_audit"]["is_reliable"] is False


def test_allocate_portfolio_budget():
    budget = 5000000  # 5 Milhões
    candidates = [
        {"item_id": "T4_BAG", "buy_price": 4000, "sell_price": 7000, "daily_volume": 1000},
        {"item_id": "T5_BAG", "buy_price": 15000, "sell_price": 25000, "daily_volume": 500},
        {"item_id": "T6_MAIN_SWORD", "buy_price": 50000, "sell_price": 85000, "daily_volume": 200},
    ]

    res = albion_allocate_portfolio_budget(
        budget=budget,
        candidate_items=candidates,
        max_items_count=3,
        has_premium=True,
        max_budget_per_item_pct=40.0
    )

    assert res["total_invested"] <= budget
    assert res["cash_reserve_leftover"] >= 0
    assert res["total_invested"] + res["cash_reserve_leftover"] == budget
    assert res["total_projected_net_profit"] > 0
    assert res["blended_portfolio_roi_pct"] > 30.0

    # Todas as quantidades devem ser estritamente inteiras
    for alloc in res["allocations"]:
        assert isinstance(alloc["quantity_integer"], int)
        assert alloc["quantity_integer"] > 0


def test_simulate_quality_reroll():
    res = albion_simulate_quality_reroll(
        item_id="T6_MAIN_SWORD",
        current_quality=1,
        target_quality=4
    )
    assert res["tier"] == "T6"
    assert res["slot_type"] == "1H_WEAPON"
    assert res["expected_total_cost_silver"] > 0
    assert res["worst_case_95pct_cost_silver"] >= res["expected_total_cost_silver"]
    assert "decision_rule" in res


def test_calculate_exact_loadout_capacity():
    # 2000 barras T5 (0.9kg cada = 1800kg) em um Boi T5 (1400kg base + 141kg bolsa + 50kg player = 1591kg)
    # com torta T7 (+30%) e bota (+14%) = 1591 * 1.30 * 1.14 = 2357.8kg
    res = albion_calculate_exact_loadout_capacity(
        items_list=[{"item_id": "T5_METALBAR", "weight_unit_kg": 0.9, "quantity": 2000}],
        mount_id="OX_T5",
        bag_id="T5.0",
        pie_id="T7_PORK",
        boots_passive_id="COURIER_STANDARD"
    )
    assert res["total_cargo_weight_kg"] == 1800.0
    assert res["total_capacity_kg"] > 2300.0
    assert res["capacity_usage_pct"] < 100.0
    assert res["status"] == "SAFE_SPRINT"
    assert res["num_trips_needed"] == 1

    # Testando sobrecarga extrema (ex: 10.000kg)
    res_overload = albion_calculate_exact_loadout_capacity(
        items_list=[{"item_id": "T5_METALBAR", "weight_unit_kg": 0.9, "quantity": 12000}],
        mount_id="OX_T5",
        bag_id="T5.0",
        pie_id="NONE",
        boots_passive_id="NONE"
    )
    assert res_overload["capacity_usage_pct"] > 200.0
    assert res_overload["status"] == "CRITICAL_IMMOBILE"
    assert res_overload["num_trips_needed"] > 5


def test_calculate_transmutation_cost():
    res = albion_calculate_transmutation_cost(
        resource_type="ORE",
        from_tier=4,
        to_tier=5,
        quantity=50,
        from_item_buy_price=150,
        to_item_market_price=600
    )
    assert res["quantity"] == 50
    assert res["system_silver_fee_per_unit"] == 225
    assert res["total_transmute_cost_per_unit"] == 375  # 150 + 225
    # Comprar pronto custa 600, transmutar custa 375 => economia de 225 por unidade (11.250 no lote)
    assert res["is_transmutation_cheaper"] is True
    assert res["silver_saved_by_transmuting"] == (600 - 375) * 50
