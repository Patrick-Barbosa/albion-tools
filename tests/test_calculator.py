"""Fórmulas fiscais oficiais, breakeven, reroll, carga e alocação de carteira."""

import pytest

from _albion_core import calculator


def test_tax_rate_premium_vs_free():
    assert calculator.get_tax_rate(has_premium=True) == 0.04
    assert calculator.get_tax_rate(has_premium=False) == 0.08
    assert calculator.get_tax_rate() == 0.08


def test_setup_fee_constant():
    assert calculator.SETUP_FEE_RATE == 0.025


def test_buy_order_cost_applies_setup_fee():
    # 10.000 * 1.025 = 10.250
    assert calculator.calculate_buy_order_cost(10_000) == 10_250
    # Cada renovação adiciona mais 2.5% sobre o bid
    assert calculator.calculate_buy_order_cost(10_000, price_updates=1) == 10_500


def test_sell_order_proceeds_discounts_tax_and_setup():
    # Premium: 10.000 * (1 - 0.04 - 0.025) = 9.350
    assert calculator.calculate_sell_order_proceeds(10_000, has_premium=True) == 9_350
    # Sem Premium: 10.000 * (1 - 0.08 - 0.025) = 8.950
    assert calculator.calculate_sell_order_proceeds(10_000, has_premium=False) == 8_950


def test_instant_sell_has_no_setup_fee():
    assert calculator.calculate_instant_sell_proceeds(10_000, has_premium=True) == 9_600
    assert calculator.calculate_instant_sell_proceeds(10_000, has_premium=False) == 9_200


def test_trade_profit_buy_and_sell_orders():
    result = calculator.calculate_trade_profit(
        buy_price=10_000,
        sell_price=20_000,
        is_buy_order=True,
        is_sell_order=True,
        has_premium=True,
    )
    assert result["unit_cost_effective"] == 10_250
    assert result["unit_revenue_effective"] == 18_700
    assert result["unit_profit"] == 8_450
    assert result["roi_pct"] == pytest.approx(82.44, abs=0.01)


def test_trade_profit_instant_buy_and_sell():
    result = calculator.calculate_trade_profit(
        buy_price=10_000,
        sell_price=20_000,
        is_buy_order=False,
        is_sell_order=False,
        has_premium=False,
        quantity=3,
    )
    assert result["unit_cost_effective"] == 10_000
    assert result["unit_revenue_effective"] == 18_400
    assert result["total_invested"] == 30_000
    assert result["net_profit"] == 25_200


def test_breakeven_covers_fees():
    result = calculator.calculate_breakeven_prices(10_000, is_buy_order=True, has_premium=True)
    assert result["effective_cost"] == 10_250
    assert result["min_sell_order_price"] == 10_963
    assert result["min_instant_sell_price"] == 10_678
    # Vender exatamente no breakeven não pode gerar prejuízo
    assert calculator.calculate_sell_order_proceeds(
        result["min_sell_order_price"], has_premium=True
    ) >= result["effective_cost"]


def test_breakeven_target_roi_raises_price():
    base = calculator.calculate_breakeven_prices(10_000, has_premium=True)
    target = calculator.calculate_breakeven_prices(10_000, has_premium=True, target_roi_pct=20)
    assert target["min_sell_order_price"] > base["min_sell_order_price"]
    assert target["target_net_revenue"] == 12_300


def test_quality_reroll_ev_stages():
    result = calculator.calculate_quality_reroll_ev(tier=6, slot_type="ARMOR", current_quality=1, target_quality=4)
    assert [stage["stage"] for stage in result["stages"]] == ["Q1 -> Q2", "Q2 -> Q3", "Q3 -> Q4"]
    assert result["total_expected_attempts"] > 0
    assert result["expected_total_cost_silver"] > 0
    assert result["worst_case_95pct_cost_silver"] >= result["expected_total_cost_silver"]


def test_quality_reroll_same_quality_is_noop():
    result = calculator.calculate_quality_reroll_ev(tier=6, current_quality=4, target_quality=4)
    assert "error" in result
    assert result["expected_total_cost"] == 0


def test_loadout_capacity_formula():
    # (400 + 141 + 50) * 1.30 * 1.14 = 875.9
    assert calculator.calculate_loadout_capacity(
        items_list=[],
        mount_capacity_kg=400,
        bag_bonus_kg=141,
        pie_bonus_pct=30,
        boots_bonus_pct=14,
    )["total_capacity_kg"] == 875.9


def test_loadout_capacity_status_bands():
    safe = calculator.calculate_loadout_capacity(
        [{"weight_unit_kg": 1.0, "quantity": 100}], mount_capacity_kg=400, bag_bonus_kg=141
    )
    assert safe["capacity_usage_pct"] < 100
    assert safe["status"] == "SAFE_SPRINT"

    over = calculator.calculate_loadout_capacity(
        [{"weight_unit_kg": 1.0, "quantity": 1_000}], mount_capacity_kg=400, bag_bonus_kg=141
    )
    assert over["status"] == "SLOW_MOUNT"

    critical = calculator.calculate_loadout_capacity(
        [{"weight_unit_kg": 1.0, "quantity": 3_000}], mount_capacity_kg=400, bag_bonus_kg=141
    )
    assert critical["status"] == "CRITICAL_IMMOBILE"


def test_allocate_budget_respects_integer_units_and_cash():
    result = calculator.allocate_portfolio_budget(
        budget=100_000,
        candidates=[
            {"item_id": "T4_BAG", "buy_price": 4_000, "sell_price": 6_500, "daily_volume": 50},
            {"item_id": "T5_BAG", "buy_price": 20_000, "sell_price": 30_000, "daily_volume": 10},
        ],
        max_items=5,
        has_premium=True,
    )
    assert result["total_invested"] <= 100_000
    assert result["cash_reserve_leftover"] == 100_000 - result["total_invested"]
    assert all(isinstance(row["quantity_integer"], int) for row in result["allocations"])
    assert all(row["quantity_integer"] > 0 for row in result["allocations"])


def test_allocate_budget_rejects_invalid_input():
    assert "error" in calculator.allocate_portfolio_budget(0, [{"buy_price": 1, "sell_price": 2}])
    assert "error" in calculator.allocate_portfolio_budget(1_000, [])
