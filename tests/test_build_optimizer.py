"""
Testes unitários para o motor de otimização de builds por tier equivalente.
"""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock

from src.albion_mcp.core.build_optimizer import (
    resolve_item_family,
    generate_tier_equivalent_variants,
    optimize_budget_build,
    clean_item_query
)
from src.albion_mcp.tools.build_optimizer import albion_optimize_budget_build


def test_clean_item_query():
    assert clean_item_query("Machado de Guerra do Adepto") == "Machado de Guerra"
    assert clean_item_query("Capuz de Assassino do Perito") == "Capuz de Assassino"
    assert clean_item_query("Adept's Battleaxe") == "Battleaxe"
    assert clean_item_query("Botas de Soldado") == "Botas de Soldado"


def test_resolve_item_family():
    # Por nome em PT-BR
    res_axe = resolve_item_family("Machado de Guerra")
    assert res_axe is not None
    assert res_axe["base_identifier"] == "MAIN_AXE"
    assert res_axe["slot_type"] == "1H_WEAPON"

    # Por ID técnico
    res_id = resolve_item_family("T4_MAIN_AXE")
    assert res_id is not None
    assert res_id["base_identifier"] == "MAIN_AXE"

    # Por armadura / capacete
    res_hood = resolve_item_family("Capuz de Assassino")
    assert res_hood is not None
    assert res_hood["base_identifier"] == "HEAD_LEATHER_SET3"
    assert res_hood["slot_type"] == "HELMET"

    # Item inexistente
    res_none = resolve_item_family("ItemInexistenteTotalmenteFalso123")
    assert res_none is None


def test_generate_tier_equivalent_variants():
    # T7 equivalente para MAIN_AXE
    variants_t7 = generate_tier_equivalent_variants("MAIN_AXE", 7)
    labels = [v["tier_enchant_label"] for v in variants_t7]
    assert "4.3" in labels
    assert "5.2" in labels
    assert "6.1" in labels
    assert "7.0" in labels

    flat_variants = [v for v in variants_t7 if v["is_flat"]]
    assert len(flat_variants) == 1
    assert flat_variants[0]["tier_enchant_label"] == "7.0"
    assert flat_variants[0]["item_id"] == "T7_MAIN_AXE"

    # T8 equivalente para MAIN_AXE
    variants_t8 = generate_tier_equivalent_variants("MAIN_AXE", 8)
    labels_t8 = [v["tier_enchant_label"] for v in variants_t8]
    assert "4.4" in labels_t8
    assert "5.3" in labels_t8
    assert "6.2" in labels_t8
    assert "7.1" in labels_t8
    assert "8.0" in labels_t8


def test_optimize_budget_build_mocked_prices():
    async def _test():
        # Simula cotações onde 5.2 é mais barato que 7.0
        mock_prices = [
            {"item_id": "T4_MAIN_AXE@3", "city": "Lymhurst", "quality": 1, "sell_price_min": 150000, "buy_price_max": 100000},
            {"item_id": "T5_MAIN_AXE@2", "city": "Lymhurst", "quality": 1, "sell_price_min": 90000, "buy_price_max": 80000},
            {"item_id": "T6_MAIN_AXE@1", "city": "Lymhurst", "quality": 1, "sell_price_min": 110000, "buy_price_max": 95000},
            {"item_id": "T7_MAIN_AXE", "city": "Lymhurst", "quality": 1, "sell_price_min": 180000, "buy_price_max": 140000},
        ]

        with patch("src.albion_mcp.core.build_optimizer.aodp_client.get_current_prices", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_prices

            res = await optimize_budget_build(
                items=["Machado de Guerra"],
                target_tier_equivalent=7,
                city="Lymhurst",
                price_mode="live"
            )

            assert "error" not in res
            assert res["city"] == "Lymhurst"
            assert res["target_tier_equivalent"] == 7

            pieces = res["build_pieces"]
            assert len(pieces) == 1
            axe_piece = pieces[0]

            # Recomendado deve ser 5.2 (90.000 prata)
            assert axe_piece["recommended"]["tier_enchant"] == "5.2"
            assert axe_piece["recommended"]["price"] == 90000
            assert axe_piece["flat_reference"]["price"] == 180000

            # Economia calculada: 180.000 - 90.000 = 90.000 (50.0%)
            assert axe_piece["recommended"]["savings_vs_flat"] == 90000
            assert axe_piece["recommended"]["savings_vs_flat_pct"] == 50.0

            summary = res["summary"]
            assert summary["total_optimized_cost"] == 90000
            assert summary["total_flat_cost"] == 180000
            assert summary["total_savings_silver"] == 90000
            assert summary["total_savings_pct"] == 50.0

    asyncio.run(_test())


def test_albion_optimize_budget_build_validation():
    async def _test():
        # Lista vazia
        res_empty = await albion_optimize_budget_build(
            items=[],
            target_tier_equivalent=7,
            city="Lymhurst"
        )
        assert "error" in res_empty

        # Tier inválido
        res_invalid_tier = await albion_optimize_budget_build(
            items=["Machado de Guerra"],
            target_tier_equivalent=12,
            city="Lymhurst"
        )
        assert "error" in res_invalid_tier

    asyncio.run(_test())
