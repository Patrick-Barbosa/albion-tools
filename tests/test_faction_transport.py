"""
Testes unitários para o Motor de Transporte de Facção e Economia de Corações (faction_transport.py).
"""

try:
    import pytest
except ImportError:
    pytest = None
from src.albion_mcp.core.faction_transport import (
    FACTION_PACK_SPECS,
    TOPOLOGY_MAP,
    calculate_faction_route_reward,
    get_route_category,
    evaluate_transmute_arbitrage,
    simulate_post_trip_decision_tree,
    validate_faction_inputs,
    calculate_faction_transport_plan
)


def test_faction_pack_weights():
    # Validação rigorosa dos pesos derivados das medições do jogador (Base 50 kg)
    # 3 corações -> 250% = 125 kg
    assert FACTION_PACK_SPECS[3]["weight_kg"] == 125.0
    # 7 corações -> 1336% = 668 kg
    assert FACTION_PACK_SPECS[7]["weight_kg"] == 668.0
    # 15 corações -> 3246% = 1623 kg
    assert FACTION_PACK_SPECS[15]["weight_kg"] == 1623.0


def test_route_rewards_matrix():
    # Origem Lymhurst:
    # Caerleon: 3->6, 7->11, 15->21
    assert calculate_faction_route_reward("Lymhurst", "Caerleon", 3) == 6
    assert calculate_faction_route_reward("Lymhurst", "Caerleon", 7) == 11
    assert calculate_faction_route_reward("Lymhurst", "Caerleon", 15) == 21

    # Vizinhas (Bridgewatch, Fort Sterling): 3->4, 7->9, 15->18
    assert calculate_faction_route_reward("Lymhurst", "Bridgewatch", 3) == 4
    assert calculate_faction_route_reward("Lymhurst", "Bridgewatch", 7) == 9
    assert calculate_faction_route_reward("Lymhurst", "Bridgewatch", 15) == 18

    # Intermediária (Thetford): 3->5, 7->11, 15->21
    assert calculate_faction_route_reward("Lymhurst", "Thetford", 3) == 5
    assert calculate_faction_route_reward("Lymhurst", "Thetford", 7) == 11
    assert calculate_faction_route_reward("Lymhurst", "Thetford", 15) == 21

    # Extrema Oposta (Martlock): 3->5, 7->12, 15->22
    assert calculate_faction_route_reward("Lymhurst", "Martlock", 3) == 5
    assert calculate_faction_route_reward("Lymhurst", "Martlock", 7) == 12
    assert calculate_faction_route_reward("Lymhurst", "Martlock", 15) == 22


def test_transmute_arbitrage_math():
    # Cenário 1: Arbóreo está caro (60.000) e Sombrio está a 50.000
    # Venda líquida do sombrio (com premium 4%): 50000 * 0.96 = 48000
    # Custo efetivo de transmutar: 48000 + 5780 = 53780
    # Como comprar no mercado custa 60000 > 53780, recomendação deve ser TRANSMUTE!
    res1 = evaluate_transmute_arbitrage(
        origin_heart_ask_price=60000,
        shadowheart_bid_price=50000,
        has_premium=True
    )
    assert res1["recommendation"] == "TRANSMUTE"
    assert res1["delta_silver_per_heart"] == 60000 - 53780

    # Cenário 2: Sombrio está hiper-valorizado (80.000) e Arbóreo barato (40.000)
    # Venda líquida do sombrio: 80000 * 0.96 = 76800
    # Custo transmutar: 76800 + 5780 = 82580
    # Comprar no mercado custa 40000 < 82580 -> recomendação deve ser SELL_AND_BUY_MARKET!
    res2 = evaluate_transmute_arbitrage(
        origin_heart_ask_price=40000,
        shadowheart_bid_price=80000,
        has_premium=True
    )
    assert res2["recommendation"] == "SELL_AND_BUY_MARKET"
    assert res2["delta_silver_per_heart"] < 0


def test_guardrails_validation():
    # Cidade inválida
    inv1 = validate_faction_inputs(
        current_city="InvalidCity",
        available_silver=100000,
        risk_profile="SAFE_ONLY",
        has_premium=True,
        mount_type="T5_BOAR",
        session_mode="CONTINUOUS_LOOP"
    )
    assert inv1["is_valid"] is False
    assert any("current_city" in e for e in inv1["errors"])

    # Saldo negativo
    inv2 = validate_faction_inputs(
        current_city="Lymhurst",
        available_silver=-50,
        risk_profile="SAFE_ONLY",
        has_premium=True,
        mount_type="T5_BOAR",
        session_mode="CONTINUOUS_LOOP"
    )
    assert inv2["is_valid"] is False
    assert any("available_silver" in e for e in inv2["errors"])

    # Válido
    val = validate_faction_inputs(
        current_city="Lymhurst",
        available_silver=500000,
        risk_profile="ALLOW_RED_ZONE",
        has_premium=True,
        mount_type="T5_BOAR",
        session_mode="CONTINUOUS_LOOP"
    )
    assert val["is_valid"] is True


def test_full_transport_plan_lymhurst():
    res = calculate_faction_transport_plan(
        current_city="Lymhurst",
        available_silver=1000000,
        risk_profile="ALLOW_RED_ZONE",
        mount_type="T5_BOAR",
        pack_size=7
    )
    assert res["status"] == "SUCCESS"
    assert res["loadout_feasibility"]["is_current_mount_sufficient"] is True
    assert res["best_route_recommended"]["destination_city"] == "Caerleon"
    assert res["best_route_recommended"]["hearts_out"] == 11
    assert res["best_route_recommended"]["hearts_delta"] == 4
