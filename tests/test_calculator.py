"""
Testes unitários para regras fiscais e financeiras (BUSINESS_RULES.md).
"""

from src.albion_mcp.core.calculator import (
    calculate_buy_order_cost,
    calculate_sell_order_proceeds,
    calculate_instant_sell_proceeds,
    calculate_trade_profit,
    format_silver,
    format_silver_compact,
)


def test_tax_rates_and_setup_fee():
    # Buy order: 1000 + 2.5% = 1025
    assert calculate_buy_order_cost(1000) == 1025

    # Instant sell (venda direta para Black Market ou Buy Order):
    # Com premium: 1000 * (1 - 0.04) = 960
    assert calculate_instant_sell_proceeds(1000, has_premium=True) == 960
    # Sem premium: 1000 * (1 - 0.08) = 920
    assert calculate_instant_sell_proceeds(1000, has_premium=False) == 920

    # Sell order (com setup fee de 2.5%):
    # Com premium: 1000 * (1 - 0.04 - 0.025) = 935
    assert calculate_sell_order_proceeds(1000, has_premium=True) == 935
    # Sem premium: 1000 * (1 - 0.08 - 0.025) = 895
    assert calculate_sell_order_proceeds(1000, has_premium=False) == 895


def test_trade_profit():
    # Compra por 1000 (buy order -> 1025) e venda por 2000 (sell order sem premium -> 1790)
    profit = calculate_trade_profit(
        buy_price=1000,
        sell_price=2000,
        is_buy_order=True,
        is_sell_order=True,
        has_premium=False,
        quantity=1
    )
    assert profit["unit_cost_effective"] == 1025
    assert profit["unit_revenue_effective"] == 1790
    assert profit["net_profit"] == 765
    assert profit["roi_pct"] > 70.0


def test_silver_formatters():
    assert format_silver(1250000) == "1.250.000 🪙"
    assert format_silver_compact(1500000) == "1.50M 🪙"
    assert format_silver_compact(25000) == "25.0k 🪙"
