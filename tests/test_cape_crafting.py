"""Manufatura de capas de facção a partir dos corações recebidos."""

import pytest

from _albion_core import cape_crafting as cc


def test_resolve_cape_by_city():
    assert cc.resolve_cape_metadata("Lymhurst")["cape_id"] == "CAPEITEM_FW_LYMHURST"
    assert cc.resolve_cape_metadata("Fort Sterling")["cape_id"] == "CAPEITEM_FW_FORTSTERLING"


def test_resolve_cape_by_alias():
    assert cc.resolve_cape_metadata("Contrabandista")["cape_id"] == "CAPEITEM_SMUGGLER"
    assert cc.resolve_cape_metadata("Morta-Viva")["cape_id"] == "CAPEITEM_UNDEAD"
    assert cc.resolve_cape_metadata("Herege")["cape_id"] == "CAPEITEM_HERETIC"


def test_resolve_cape_by_item_id():
    assert cc.resolve_cape_metadata("CAPEITEM_MORGANA")["cape_id"] == "CAPEITEM_MORGANA"


def test_resolve_cape_rejects_unknown():
    with pytest.raises(ValueError):
        cc.resolve_cape_metadata("Capa Inexistente")


def test_eligible_capes_for_royal_heart():
    capes = [cape["cape_id"] for cape in cc.get_eligible_capes_for_heart("Lymhurst")]
    assert capes == ["CAPEITEM_FW_LYMHURST", "CAPEITEM_HERETIC"]


def test_eligible_capes_for_shadow_heart():
    capes = [cape["cape_id"] for cape in cc.get_eligible_capes_for_heart("Caerleon")]
    assert capes == ["CAPEITEM_FW_CAERLEON", "CAPEITEM_SMUGGLER"]


def test_crafting_cost_uses_correct_tier_enchantment():
    cost = cc.calculate_cape_crafting_cost(
        city_faction="Lymhurst",
        tier=4,
        enchantment=2,
        heart_unit_cost=45_000,
    )
    assert cost["cape_id"] == "CAPEITEM_FW_LYMHURST"
    assert cost["cape_full_id"] == "T4_CAPEITEM_FW_LYMHURST@2"
    assert cost["tier"] == 4
    assert cost["enchantment"] == 2


def test_crafting_cost_rejects_invalid_tier_and_enchantment():
    with pytest.raises(ValueError):
        cc.calculate_cape_crafting_cost("Lymhurst", tier=9)
    with pytest.raises(ValueError):
        cc.calculate_cape_crafting_cost("Lymhurst", tier=4, enchantment=4)


def test_optimize_returns_best_cape_for_heart():
    result = cc.optimize_cape_crafting_for_heart(
        heart_or_city="Lymhurst",
        tier=4,
        enchantment=2,
        heart_market_price=45_000,
        has_premium=True,
    )
    assert result["best_cape_id"] in ("CAPEITEM_FW_LYMHURST", "CAPEITEM_HERETIC")
    assert result["best_cape_name"]
    assert "heart_evaluated" in result
