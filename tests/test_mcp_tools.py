"""
Testes de integração para as ferramentas do Servidor MCP.
"""

import pytest
from src.albion_mcp.tools.items import albion_search_items, albion_get_item_details
from src.albion_mcp.tools.economics import (
    albion_calculate_tax_and_fees,
    albion_simulate_enchantment,
    albion_calculate_refining,
    albion_calculate_cascade_refining
)
from src.albion_mcp.tools.market_live import albion_get_api_quota_status
from src.albion_mcp.tools.databricks_tools import albion_databricks_status


def test_tool_search_items():
    res = albion_search_items(query="Espada", tier="T4", limit=5)
    assert res["total_found"] > 0
    assert len(res["items"]) <= 5
    assert "T4" in res["items"][0]["tier"]


def test_tool_get_item_details():
    res = albion_get_item_details("T4_BAG")
    assert res["item_id"] == "T4_BAG"
    assert res["slot_type"] == "BAG"
    assert res["enchant_materials_per_level"] == 192


def test_tool_calculate_tax_and_fees():
    res = albion_calculate_tax_and_fees(
        buy_price=50000,
        sell_price=80000,
        is_buy_order=True,
        is_sell_order=True,
        has_premium=True,
        quantity=2
    )
    assert res["unit_cost_effective"] == 51250
    assert res["unit_revenue_effective"] == 74800  # 80000 * (1 - 0.04 - 0.025)
    assert res["net_profit"] == (74800 - 51250) * 2
    assert res["roi_pct"] > 0


def test_tool_simulate_enchantment():
    # Simula T4.0 Bolsa -> T4.1 Bolsa
    res = albion_simulate_enchantment(
        base_item_id="T4_BAG",
        target_enchantment=1,
        base_item_buy_price=5000,
        material_unit_price=20,
        target_item_sell_price=15000,
        has_premium=True
    )
    assert res["enchantment"]["materials_required"] == 192
    assert res["financial_summary"]["net_profit"] > 0
    assert "Lucrativo" in res["financial_summary"]["verdict"]


def test_tool_calculate_refining():
    res = albion_calculate_refining(
        resource_type="ORE",
        tier=5,
        enchantment=0,
        has_focus=False,
        has_premium=True
    )
    assert res["resource"] == "ORE"
    assert res["specialized_city"] == "Thetford"
    assert res["economics"]["rrr_pct"] == 40.0


def test_tool_calculate_cascade_refining():
    res = albion_calculate_cascade_refining(
        resource_type="WOOD",
        target_tier=6,
        target_enchantment=0,
        budget=1000000,
        has_focus=False,
        has_premium=False
    )
    assert res["resource"] == "WOOD"
    assert res["refining_city"] == "Fort Sterling"
    assert "cargo" in res
    assert "recommended_mount" in res["cargo"]


def test_tool_quota_status():
    status = albion_get_api_quota_status()
    assert "aodp_rest_rate_limiter" in status
    assert "nats_firehose_stream" in status
    assert "recommendation" in status


def test_tool_databricks_status():
    status = albion_databricks_status()
    assert "configured" in status
    assert "status" in status
