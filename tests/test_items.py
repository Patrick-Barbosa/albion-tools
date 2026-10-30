"""Busca de itens e resolução do universo de varredura (offline)."""

from _albion_core import items


def test_search_items_returns_matches():
    result = items.search_items("Bolsa", limit=5)
    assert result["total_found"] > 0
    assert all("item_id" in row for row in result["items"])


def test_search_items_respects_limit():
    assert items.search_items("Bolsa", limit=2)["total_found"] <= 2


def test_item_details_includes_enchantment_rules():
    details = items.item_details("T6_MAIN_SWORD")
    assert details["item_id"] == "T6_MAIN_SWORD"
    assert details["tier"] == "T6"
    assert details["enchant_materials_per_level"] == 288
    assert ".0_to_.1" in details["enchantment_rules"]


def test_item_details_unknown_returns_error():
    result = items.item_details("T9_ITEM_INEXISTENTE")
    assert "error" in result


def test_resolve_universe_filters_category():
    universe = items.resolve_universe(category="Bolsas & Capas", limit=10)
    assert universe
    assert all("CAPE" in item or "BAG" in item for item in universe)


def test_resolve_universe_filters_tier():
    universe = items.resolve_universe(tier="T5", limit=10)
    assert universe
    assert all(item.startswith("T5_") for item in universe)


def test_resolve_universe_respects_limit():
    assert len(items.resolve_universe(limit=3)) == 3
