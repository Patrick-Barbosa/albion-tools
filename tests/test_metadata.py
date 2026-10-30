"""Catálogo local de itens: nomes PT-BR/EN, tier, encantamento e insumos."""

import pytest

from _albion_core.metadata import metadata_manager


@pytest.fixture(autouse=True)
def _catalog():
    metadata_manager.ensure_data_loaded()


def test_catalog_is_loaded():
    assert len(metadata_manager.item_names) > 100


def test_item_name_pt_br():
    assert metadata_manager.get_item_name("T4_BAG") == "Bolsa do Adepto"


def test_item_name_en():
    assert metadata_manager.get_item_name_en("T4_BAG") == "Adept's Bag"


def test_unknown_item_falls_back_to_synthesized_name():
    # O catálogo sintetiza um nome legível a partir do ID quando o item não existe.
    assert metadata_manager.get_item_name("T9_ITEM_INEXISTENTE") == "T9 T9 Item Inexistente"


def test_tier_and_enchantment_parsing():
    assert metadata_manager.get_tier("T6_MAIN_SWORD@2") == "T6"
    assert metadata_manager.get_enchantment_level("T6_MAIN_SWORD@2") == 2
    assert metadata_manager.get_enchantment_level("T4_BAG") == 0


def test_slot_types():
    assert metadata_manager.get_slot_type("T4_BAG") == "BAG"
    assert metadata_manager.get_slot_type("T6_MAIN_SWORD") == "1H_WEAPON"
    assert metadata_manager.get_slot_type("T5_2H_AXE") == "2H_WEAPON"
    assert metadata_manager.get_slot_type("T5_ARMOR_PLATE_SET1") == "ARMOR"
    assert metadata_manager.get_slot_type("T5_HELMET_PLATE_SET1") == "HELMET"
    assert metadata_manager.get_slot_type("T5_SHOES_PLATE_SET1") == "BOOTS"


def test_enchantment_material_costs_are_multiples_of_96():
    assert metadata_manager.get_enchantment_cost("T5_2H_AXE") == 384
    assert metadata_manager.get_enchantment_cost("T5_MAIN_SWORD") == 288
    assert metadata_manager.get_enchantment_cost("T5_ARMOR_PLATE_SET1") == 192
    assert metadata_manager.get_enchantment_cost("T4_BAG") == 192
    assert metadata_manager.get_enchantment_cost("T5_HELMET_PLATE_SET1") == 96
    for item_id in ("T5_2H_AXE", "T5_MAIN_SWORD", "T5_ARMOR_PLATE_SET1", "T4_BAG", "T5_HELMET_PLATE_SET1"):
        assert metadata_manager.get_enchantment_cost(item_id) % 96 == 0


def test_category_mapping():
    assert metadata_manager.get_category_for_item("T4_BAG") == "Bolsas & Capas"
    assert metadata_manager.get_category_for_item("T6_MAIN_SWORD") == "Armas"
    assert metadata_manager.get_category_for_item("T6_ARMOR_PLATE_SET1") == "Armaduras"


def test_search_items_by_partial_name():
    results = metadata_manager.search_items("Bolsa", limit=5)
    assert results
    assert all("Bolsa" in row["name_pt"] or "Bolsa" in row["item_id"] for row in results)


def test_search_items_filters_by_tier():
    results = metadata_manager.search_items("Bolsa", tier="T5", limit=10)
    assert results
    assert all(row["tier"] == "T5" for row in results)


def test_icon_url_points_to_render_service():
    assert metadata_manager.get_icon_url("T4_BAG").startswith("https://render.albiononline.com/v1/item/T4_BAG.png")
