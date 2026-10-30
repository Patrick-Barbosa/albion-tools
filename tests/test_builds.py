"""Resolução de famílias e geração de variantes por tier equivalente (offline)."""

import pytest

from _albion_core import builds


def test_resolve_family_from_pt_name():
    family = builds.resolve_item_family("Machado de Guerra")
    assert family["base_identifier"] == "MAIN_AXE"
    assert family["slot_type"] == "1H_WEAPON"


def test_resolve_family_from_en_name():
    family = builds.resolve_item_family("Mercenary Jacket")
    assert family["base_identifier"] == "ARMOR_LEATHER_SET1"


def test_resolve_family_from_item_id():
    family = builds.resolve_item_family("T4_MAIN_AXE")
    assert family["base_identifier"] == "MAIN_AXE"


def test_resolve_family_unknown_returns_none():
    assert builds.resolve_item_family("Item Que Nao Existe 123") is None


def test_variants_for_t7_equivalent():
    variants = builds.generate_tier_equivalent_variants("MAIN_AXE", 7)
    assert [variant["item_id"] for variant in variants] == [
        "T4_MAIN_AXE@3",
        "T5_MAIN_AXE@2",
        "T6_MAIN_AXE@1",
        "T7_MAIN_AXE",
    ]


def test_variants_for_t6_equivalent():
    variants = builds.generate_tier_equivalent_variants("MAIN_AXE", 6)
    assert [variant["item_id"] for variant in variants] == [
        "T4_MAIN_AXE@2",
        "T5_MAIN_AXE@1",
        "T6_MAIN_AXE",
    ]


def test_variants_are_ordered_from_cheapest_tier_to_highest():
    variants = builds.generate_tier_equivalent_variants("ARMOR_LEATHER_SET1", 8)
    tiers = [variant["tier"] for variant in variants]
    assert tiers == sorted(tiers)
    assert len(variants) == 5


def test_variants_empty_when_target_below_minimum_tier():
    assert builds.generate_tier_equivalent_variants("MAIN_AXE", 3) == []
