"""Rotas de facção, recompensas por fardo, transmutação e guardrails."""

import pytest

from _albion_core import faction_transport as ft


def test_route_categories_between_royal_cities():
    assert ft.get_route_category("Lymhurst", "Thetford") == ("INTERMEDIATE", "SAFE_ZONES")
    assert ft.get_route_category("Lymhurst", "Fort Sterling") == ("NEIGHBOR", "SAFE_ZONES")


def test_route_to_caerleon_is_red_zone():
    category, risk = ft.get_route_category("Lymhurst", "Caerleon")
    assert category == "CAERLEON"
    assert risk == "RED_ZONE_FULL_LOOT"


def test_route_category_rejects_unknown_origin():
    with pytest.raises(ValueError):
        ft.get_route_category("Atlantis", "Lymhurst")


@pytest.mark.parametrize("pack_size,expected", [(3, 5), (7, 11), (15, 21)])
def test_faction_route_reward(pack_size, expected):
    assert ft.calculate_faction_route_reward("Lymhurst", "Thetford", pack_size) == expected


def test_faction_route_reward_rejects_invalid_pack():
    with pytest.raises(ValueError):
        ft.calculate_faction_route_reward("Lymhurst", "Thetford", 4)


def test_transmute_arbitrage_recommends_transmute_when_market_is_expensive():
    result = ft.evaluate_transmute_arbitrage(
        origin_heart_ask_price=90_000,
        shadowheart_bid_price=60_000,
        has_premium=True,
    )
    assert result["recommendation"] == "TRANSMUTE"
    assert result["delta_silver_per_heart"] > 0
    assert result["shadowheart_net_sell"] == 57_600
    assert result["effective_transmute_cost"] == 57_600 + ft.TRANSMUTE_FEE_SILVER


def test_transmute_arbitrage_recommends_market_when_shadowheart_is_expensive():
    result = ft.evaluate_transmute_arbitrage(
        origin_heart_ask_price=50_000,
        shadowheart_bid_price=60_000,
        has_premium=True,
    )
    assert result["recommendation"] == "SELL_AND_BUY_MARKET"
    assert result["delta_silver_per_heart"] < 0


def test_validate_faction_inputs_accepts_valid_player():
    result = ft.validate_faction_inputs(
        current_city="Lymhurst",
        available_silver=1_000_000,
        risk_profile="SAFE_ONLY",
        has_premium=True,
        mount_type="T5_BOAR",
        session_mode="CONTINUOUS_LOOP",
        pack_size=7,
    )
    assert result["is_valid"] is True
    assert result["normalized_city"] == "Lymhurst"
    assert result["errors"] == []


def test_validate_faction_inputs_rejects_missing_reality():
    result = ft.validate_faction_inputs(
        current_city="Atlantis",
        available_silver=-1,
        risk_profile="YOLO",
        has_premium=None,
        mount_type="",
        session_mode="FAST",
        pack_size=4,
    )
    assert result["is_valid"] is False
    assert len(result["errors"]) >= 6


def test_transport_plan_is_offline_with_mock_prices(monkeypatch):
    from _albion_core import hearts

    # Sem rede: a API devolve vazio e o motor cai na hierarquia MANUAL.
    monkeypatch.setattr(hearts.aodp, "get_prices", lambda *args, **kwargs: [])

    plan = hearts.calculate_faction_transport(
        current_city="Lymhurst",
        available_silver=1_000_000,
        risk_profile="SAFE_ONLY",
        has_premium=True,
        mount_type="T5_BOAR",
        session_mode="CONTINUOUS_LOOP",
        pack_size=7,
        target_destination="Thetford",
        origin_heart_price=45_000,
        shadowheart_price=42_000,
    )
    assert plan["status"] == "SUCCESS"
    assert plan["origin_city"] == "Lymhurst"
    assert plan["pack_spec"]["hearts_in"] == 7
    assert plan["price_audit"]["hierarchy_applied"] == "API > MANUAL"
    assert plan["price_audit"]["price_source"] == "MANUAL"
    assert plan["definitive_verdict"]
    assert plan["price_statement_markdown"]


def test_transport_plan_blocks_invalid_risk_destination():
    plan = ft.calculate_faction_transport_plan(
        current_city="Lymhurst",
        available_silver=1_000_000,
        risk_profile="SAFE_ONLY",
        has_premium=True,
        mount_type="T5_BOAR",
        session_mode="CONTINUOUS_LOOP",
        pack_size=7,
        target_destination="Caerleon",
        mock_heart_prices={},
        material_prices={},
    )
    assert plan["status"] == "DESTINATION_BLOCKED_BY_RISK_OR_INVALID"


def test_transport_plan_rejects_invalid_parameters():
    plan = ft.calculate_faction_transport_plan(
        current_city="Lymhurst",
        available_silver=1_000_000,
        risk_profile="SAFE_ONLY",
        has_premium=True,
        mount_type="T5_BOAR",
        session_mode="CONTINUOUS_LOOP",
        pack_size=4,
    )
    assert plan["status"] == "GUARDRAIL_VALIDATION_FAILED"
