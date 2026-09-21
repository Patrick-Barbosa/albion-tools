"""
Core do Albion Online Market Intelligence MCP.
"""

from .rate_limiter import rate_limiter, RateLimitExceededException
from .calculator import (
    PREMIUM_TAX,
    NON_PREMIUM_TAX,
    SETUP_FEE_RATE,
    ENCHANT_SLOT_COSTS,
    get_tax_rate,
    calculate_buy_order_cost,
    calculate_sell_order_proceeds,
    calculate_instant_sell_proceeds,
    calculate_trade_profit,
    format_silver,
    format_silver_compact,
)
from .metadata import metadata_manager, QUALITY_NAMES, CITIES, SAFE_ROYAL_CITIES, CATEGORIES, TIERS
try:
    from .aodp_client import aodp_client
except ImportError:
    aodp_client = None

try:
    from .nats_client import nats_subscriber
except ImportError:
    nats_subscriber = None

try:
    from .databricks_client import databricks_client
except ImportError:
    databricks_client = None

try:
    from .polars_analytics import analytics_engine
except ImportError:
    analytics_engine = None

from .loadout_optimizer import solve_cheapest_loadout, calculate_effective_capacity
from .faction_transport import calculate_faction_transport_plan, simulate_post_trip_decision_tree
from .cape_crafting import calculate_cape_crafting_cost, evaluate_cape_vs_raw_heart_profit

__all__ = [
    "rate_limiter",
    "RateLimitExceededException",
    "PREMIUM_TAX",
    "NON_PREMIUM_TAX",
    "SETUP_FEE_RATE",
    "ENCHANT_SLOT_COSTS",
    "get_tax_rate",
    "calculate_buy_order_cost",
    "calculate_sell_order_proceeds",
    "calculate_instant_sell_proceeds",
    "calculate_trade_profit",
    "format_silver",
    "format_silver_compact",
    "metadata_manager",
    "QUALITY_NAMES",
    "CITIES",
    "SAFE_ROYAL_CITIES",
    "CATEGORIES",
    "TIERS",
    "aodp_client",
    "nats_subscriber",
    "databricks_client",
    "analytics_engine",
    "solve_cheapest_loadout",
    "calculate_effective_capacity",
    "calculate_faction_transport_plan",
    "simulate_post_trip_decision_tree",
    "calculate_cape_crafting_cost",
    "evaluate_cape_vs_raw_heart_profit",
]
