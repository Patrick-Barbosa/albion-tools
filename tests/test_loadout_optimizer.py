"""
Testes unitários para o Motor Universal de Carga e Montarias (loadout_optimizer.py).
"""

try:
    import pytest
except ImportError:
    pytest = None
from src.albion_mcp.core.loadout_optimizer import (
    calculate_effective_capacity,
    solve_cheapest_loadout,
    MOUNTS_CATALOG,
    BAGS_CATALOG,
    FOOD_CATALOG
)


def test_effective_capacity_formula():
    # Base 50 kg + Boi T5 (1400 kg) + Bolsa T5.1 (180 kg) = 1630 kg
    # Torta T7 (+30%) * Bota (+14%) = 1.30 * 1.14 = 1.482
    # 1630 * 1.482 = 2415.66 -> round 2415.7 kg
    cap = calculate_effective_capacity(
        mount_capacity_kg=1400.0,
        bag_bonus_kg=180.0,
        pie_bonus_pct=30.0,
        boots_bonus_pct=14.0,
        player_base_kg=50.0
    )
    assert cap == 2415.7


def test_solve_cheapest_for_light_pack():
    # Fardo Leve: 125 kg
    # Deve ser resolvível por montarias baratas (ex: Cavalo T4 ou Boi T4)
    res = solve_cheapest_loadout(target_weight_kg=125.0)
    assert res["status"] == "SUCCESS"
    assert res["cheapest_loadout"]["effective_capacity_kg"] >= 125.0
    assert res["cheapest_loadout"]["usage_pct"] <= 100.0


def test_solve_cheapest_for_medium_pack_boar():
    # Fardo Médio: 668 kg
    # Jogador possui Javali T5 (current_mount='T5_BOAR')
    res = solve_cheapest_loadout(
        target_weight_kg=668.0,
        current_mount_id="T5_BOAR",
        risk_level="ALLOW_RED_ZONE"
    )
    assert res["status"] == "SUCCESS"
    assert res["is_current_mount_sufficient"] is True
    assert res["current_mount_solution"]["mount_id"] == "T5_BOAR"
    assert res["current_mount_solution"]["usage_pct"] <= 100.0
    assert res["current_mount_solution"]["is_passive"] is True


def test_solve_cheapest_for_heavy_pack():
    # Fardo Pesado: 1623 kg
    # Jogador não tem montaria pesada: o solver deve sugerir Boi T5 com combo barato ou Boi T6
    res = solve_cheapest_loadout(target_weight_kg=1623.0, risk_level="SAFE_ONLY")
    assert res["status"] == "SUCCESS"
    loadout = res["cheapest_loadout"]
    assert loadout["effective_capacity_kg"] >= 1623.0
    assert loadout["usage_pct"] <= 100.0
    # O custo deve ser infinitamente menor do que comprar um Mamute ou Boi T8
    assert loadout["total_cost_silver"] < 200000


def test_red_zone_risk_filter():
    # Em Red Zone, cavalos e garras (carga ativa) devem ser descartados
    res = solve_cheapest_loadout(target_weight_kg=200.0, risk_level="ALLOW_RED_ZONE")
    assert res["status"] == "SUCCESS"
    assert res["cheapest_loadout"]["mount_is_passive"] is True
