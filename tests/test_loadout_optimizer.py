"""Física de carga e solver de kit de transporte mais barato."""

import pytest

from _albion_core import loadout_optimizer as lo


def test_effective_capacity_is_multiplicative():
    # (400 + 141 + 50) * 1.30 * 1.14 = 875.9
    assert lo.calculate_effective_capacity(
        mount_capacity_kg=400,
        bag_bonus_kg=141,
        pie_bonus_pct=30,
        boots_bonus_pct=14,
    ) == 875.9


def test_effective_capacity_without_bonuses():
    # Padrões: torta 0% e passiva de bota 14% -> (100 + 0 + 50) * 1.14 = 171.0
    assert lo.calculate_effective_capacity(100) == 171.0


def test_solver_finds_loadout_under_capacity():
    result = lo.solve_cheapest_loadout(target_weight_kg=700, current_mount_id="T5_BOAR", risk_level="SAFE_ONLY")
    best = result["cheapest_loadout"]
    assert best["effective_capacity_kg"] >= 700
    assert best["usage_pct"] <= 100.0
    assert result["status"] == "SUCCESS"


def test_solver_reuses_owned_mount():
    result = lo.solve_cheapest_loadout(target_weight_kg=700, current_mount_id="T5_BOAR")
    best = result["cheapest_loadout"]
    assert best["mount_id"] == "T5_BOAR"
    assert best["mount_already_owned"] is True
    assert best["mount_cost_silver"] == 0


def test_solver_red_zone_only_uses_passive_mounts():
    result = lo.solve_cheapest_loadout(target_weight_kg=3_000, risk_level="ALLOW_RED_ZONE")
    best = result["cheapest_loadout"]
    assert best["mount_is_passive"] is True


def test_solver_reports_savings_vs_naive_mount():
    result = lo.solve_cheapest_loadout(target_weight_kg=700)
    assert result["silver_saved_vs_naive_mount"] >= 0
    assert result["naive_pure_mount_comparison"]


def test_solver_impossible_weight_returns_status():
    result = lo.solve_cheapest_loadout(target_weight_kg=10_000_000)
    assert result["status"] == "INSUFFICIENT_CAPACITY_OR_BUDGET"
    assert "cheapest_loadout" not in result
