"""
Catálogo de ferramentas expostas pelo Servidor MCP do Albion Online.
"""

from .items import albion_search_items, albion_get_item_details
from .market_live import (
    albion_get_current_prices,
    albion_nats_get_live_orders,
    albion_get_gold_prices,
    albion_get_api_quota_status,
)
from .market_history import albion_get_price_history, albion_get_market_pareto
from .economics import (
    albion_calculate_tax_and_fees,
    albion_simulate_enchantment,
    albion_calculate_refining,
    albion_calculate_cascade_refining,
    albion_find_arbitrage_opportunities,
)
from .databricks_tools import albion_databricks_status, albion_databricks_query_gold
from .anti_hallucination import (
    albion_calculate_breakeven_price,
    albion_audit_quote_freshness_and_phantom,
    albion_allocate_portfolio_budget,
    albion_simulate_quality_reroll,
    albion_calculate_exact_loadout_capacity,
    albion_calculate_transmutation_cost,
)
from .build_optimizer import albion_optimize_budget_build
from .logistics_tools import albion_optimize_loadout_capacity
from .faction_tools import (
    albion_calculate_faction_transport,
    albion_simulate_heart_cycle,
    albion_evaluate_heart_downstream,
)

ALL_TOOLS = [
    # Metadados e catálogo
    albion_search_items,
    albion_get_item_details,
    # Mercado ao vivo e NATS
    albion_get_current_prices,
    albion_nats_get_live_orders,
    albion_get_gold_prices,
    albion_get_api_quota_status,
    # Histórico e Pareto
    albion_get_price_history,
    albion_get_market_pareto,
    # Economia, refino e arbitragem
    albion_calculate_tax_and_fees,
    albion_simulate_enchantment,
    albion_calculate_refining,
    albion_calculate_cascade_refining,
    albion_find_arbitrage_opportunities,
    # Otimização de builds
    albion_optimize_budget_build,
    # Databricks opcional
    albion_databricks_status,
    albion_databricks_query_gold,
    # Ferramentas determinísticas anti-alucinação
    albion_calculate_breakeven_price,
    albion_audit_quote_freshness_and_phantom,
    albion_allocate_portfolio_budget,
    albion_simulate_quality_reroll,
    albion_calculate_exact_loadout_capacity,
    albion_calculate_transmutation_cost,
    # Logística universal de carga
    albion_optimize_loadout_capacity,
    # Inteligência de transporte de facção
    albion_calculate_faction_transport,
    albion_simulate_heart_cycle,
    albion_evaluate_heart_downstream,
]

__all__ = [
    "ALL_TOOLS",
    "albion_search_items",
    "albion_get_item_details",
    "albion_get_current_prices",
    "albion_nats_get_live_orders",
    "albion_get_gold_prices",
    "albion_get_api_quota_status",
    "albion_get_price_history",
    "albion_get_market_pareto",
    "albion_calculate_tax_and_fees",
    "albion_simulate_enchantment",
    "albion_calculate_refining",
    "albion_calculate_cascade_refining",
    "albion_find_arbitrage_opportunities",
    "albion_optimize_budget_build",
    "albion_databricks_status",
    "albion_databricks_query_gold",
    "albion_calculate_breakeven_price",
    "albion_audit_quote_freshness_and_phantom",
    "albion_allocate_portfolio_budget",
    "albion_simulate_quality_reroll",
    "albion_calculate_exact_loadout_capacity",
    "albion_calculate_transmutation_cost",
    "albion_optimize_loadout_capacity",
    "albion_calculate_faction_transport",
    "albion_simulate_heart_cycle",
    "albion_evaluate_heart_downstream",
]
