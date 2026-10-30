"""Travas anti-alucinação: breakeven, reroll, carga, transmutação e carteira."""

import pytest

from _albion_core import anti_phantom, calculator


def test_breakeven_wrapper_matches_calculator():
    wrapped = anti_phantom.calculate_breakeven_price(10_000, is_buy_order=True, has_premium=True)
    direct = calculator.calculate_breakeven_prices(10_000, is_buy_order=True, has_premium=True)
    assert wrapped == direct


def test_breakeven_premium_is_cheaper_than_free():
    premium = anti_phantom.calculate_breakeven_price(10_000, has_premium=True)
    free = anti_phantom.calculate_breakeven_price(10_000, has_premium=False)
    assert premium["min_sell_order_price"] < free["min_sell_order_price"]


def test_quality_reroll_wrapper_enriches_item():
    result = anti_phantom.simulate_quality_reroll("T6_MAIN_SWORD", current_quality=1, target_quality=4)
    assert result["item_id"] == "T6_MAIN_SWORD"
    assert result["item_name_pt"] == "Espada Larga do Mestre"
    assert result["expected_total_cost_silver"] > 0


def test_exact_loadout_capacity_reports_kit_and_usage():
    result = anti_phantom.calculate_exact_loadout_capacity(
        [{"item_id": "T5_METALBAR", "weight_unit_kg": 0.9, "quantity": 1_500}],
        mount_id="OX_T5",
        bag_id="T5.0",
        pie_id="T7_PORK",
    )
    assert result["total_cargo_weight_kg"] == pytest.approx(1_350.0, abs=0.1)
    assert result["total_capacity_kg"] > 0
    assert result["equipped_kit"]["mount_name"]
    assert "solver_recommendation" in result


def test_loadout_capacity_flags_overload():
    result = anti_phantom.calculate_exact_loadout_capacity(
        [{"item_id": "T8_PLANKS", "weight_unit_kg": 2.8, "quantity": 10_000}],
        mount_id="OX_T5",
    )
    assert result["capacity_usage_pct"] > 100
    assert result["solver_recommendation"]["is_current_kit_sufficient"] is False


def test_transmutation_heart_fee():
    result = anti_phantom.calculate_transmutation_cost(
        resource_type="HEART",
        from_tier=4,
        to_tier=5,
        quantity=1,
        from_item_buy_price=60_000,
        to_item_market_price=90_000,
    )
    assert result["system_silver_fee_per_unit"] == 5_780
    assert result["total_transmute_cost_per_unit"] == 65_780
    assert result["is_transmutation_cheaper"] is True


def test_transmutation_ore_rejects_when_market_is_cheaper():
    # T4 -> T5 custa 225 de taxa: 150 + 225 = 375 > 300 de mercado.
    result = anti_phantom.calculate_transmutation_cost(
        resource_type="ORE",
        from_tier=4,
        to_tier=5,
        quantity=100,
        from_item_buy_price=150,
        to_item_market_price=300,
    )
    assert result["is_transmutation_cheaper"] is False
    assert result["silver_lost_by_transmuting"] > 0
    assert "NÃO TRANSMUTE" in result["verdict"]


def test_allocate_budget_wrapper_uses_integer_units():
    result = anti_phantom.allocate_budget(
        budget=100_000,
        candidate_items=[
            {"item_id": "T4_BAG", "buy_price": 4_000, "sell_price": 6_500, "daily_volume": 50}
        ],
        max_items_count=3,
        has_premium=True,
    )
    assert result["total_invested"] <= 100_000
    assert all(isinstance(row["quantity_integer"], int) for row in result["allocations"])
