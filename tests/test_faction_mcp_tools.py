"""
Testes de integração das ferramentas MCP de Logística Universal e Transporte de Facção.
"""

try:
    import pytest
except ImportError:
    class DummyMark:
        def asyncio(self, f):
            return f
    class DummyPytest:
        mark = DummyMark()
    pytest = DummyPytest()
import asyncio
from src.albion_mcp.tools.logistics_tools import albion_optimize_loadout_capacity
from src.albion_mcp.tools.faction_tools import (
    albion_calculate_faction_transport,
    albion_simulate_heart_cycle,
    albion_evaluate_heart_downstream
)
from src.albion_mcp.tools import ALL_TOOLS


def test_tools_registered_in_all_tools():
    tool_names = [fn.__name__ for fn in ALL_TOOLS]
    assert "albion_optimize_loadout_capacity" in tool_names
    assert "albion_calculate_faction_transport" in tool_names
    assert "albion_simulate_heart_cycle" in tool_names
    assert "albion_evaluate_heart_downstream" in tool_names
    # Total deve ser 26 ferramentas oficiais
    assert len(ALL_TOOLS) == 26


def test_albion_optimize_loadout_capacity_tool():
    res = albion_optimize_loadout_capacity(
        target_weight_kg=668.0,
        current_mount="T5_BOAR",
        risk_level="ALLOW_RED_ZONE"
    )
    assert res["status"] == "SUCCESS"
    assert res["is_current_mount_sufficient"] is True

    # Teste via items_list (ex: 2000 barras T5 a 0.9kg = 1800kg)
    res_items = albion_optimize_loadout_capacity(
        items_list=[{"item_id": "T5_METALBAR", "weight_unit_kg": 0.9, "quantity": 2000}],
        risk_level="SAFE_ONLY"
    )
    assert res_items["status"] == "SUCCESS"
    assert res_items["items_count"] == 1
    assert res_items["items_computed_weight_kg"] == 1800.0
    assert res_items["cheapest_loadout"]["total_capacity_kg"] >= 1800.0


def test_albion_simulate_heart_cycle_tool():
    # 6 ciclos (1 hora de jogo) de Javali T5
    res = albion_simulate_heart_cycle(
        origin_city="Lymhurst",
        destination_city="Caerleon",
        pack_size=7,
        num_cycles=6,
        origin_heart_price=45000,
        shadowheart_price=62000,
        has_premium=True
    )
    assert res["simulation_parameters"]["num_cycles"] == 6
    assert res["simulation_parameters"]["total_playtime_minutes"] == 60.0
    # 6 ciclos * 4 corações de lucro = 24 corações sombrios de lucro
    assert res["path_3_hybrid_autoloop"]["surplus_hearts_sold_for_cash"] == 24
    assert res["path_3_hybrid_autoloop"]["liquid_cash_profit_in_pocket"] > 1000000


def test_albion_evaluate_heart_downstream_tool():
    res = albion_evaluate_heart_downstream(
        city_faction="Lymhurst",
        tier=4,
        enchantment=2,
        target_quality=1,
        heart_market_price=45000,
        cape_market_sell_price=175000,
        has_premium=True
    )
    assert "recommendation" in res
    assert res["hearts_consumed"] == 1


@pytest.mark.asyncio
async def test_albion_calculate_faction_transport_tool_async():
    res = await albion_calculate_faction_transport(
        current_city="Lymhurst",
        available_silver=1000000,
        risk_profile="ALLOW_RED_ZONE",
        has_premium=True,
        mount_type="T5_BOAR",
        session_mode="CONTINUOUS_LOOP",
        pack_size=7
    )
    assert res["status"] == "SUCCESS"
    assert res["origin_city"] == "Lymhurst"
    assert res["best_route_recommended"]["destination_city"] == "Caerleon"
