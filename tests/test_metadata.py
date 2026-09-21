"""
Testes unitários para metadados e traduções em PT-BR.
"""

from src.albion_mcp.core.metadata import metadata_manager


def test_metadata_item_names_and_tiers():
    metadata_manager.ensure_data_loaded()

    # Tier T4
    assert metadata_manager.get_tier("T4_BAG") == "T4"
    assert metadata_manager.get_tier("T8_MAIN_SWORD") == "T8"

    # Encantamentos
    assert metadata_manager.get_enchantment_level("T6_MAIN_SWORD@1") == 1
    assert metadata_manager.get_enchantment_level("T7_BAG@2") == 2
    assert metadata_manager.get_enchantment_level("T4_BAG") == 0

    # Resolução de slots
    assert metadata_manager.get_slot_type("T4_2H_CROSSBOW") == "2H_WEAPON"
    assert metadata_manager.get_slot_type("T4_BAG") == "BAG"
    assert metadata_manager.get_slot_type("T5_ARMOR_PLATE_SET1") == "ARMOR"
    assert metadata_manager.get_slot_type("T4_HEAD_PLATE_SET1") == "HELMET"

    # Custos em múltiplos de 96
    assert metadata_manager.get_enchantment_cost("T4_2H_CROSSBOW") == 384
    assert metadata_manager.get_enchantment_cost("T4_BAG") == 192
    assert metadata_manager.get_enchantment_cost("T4_HEAD_PLATE_SET1") == 96


def test_metadata_search():
    metadata_manager.ensure_data_loaded()
    results = metadata_manager.search_items("Bolsa", tier="T4", limit=5)
    assert len(results) > 0
    assert any("BAG" in r["item_id"] for r in results)
