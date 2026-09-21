import sys
import os
import asyncio

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.albion_mcp.tools.market_live import albion_get_current_prices, albion_get_api_quota_status
from src.albion_mcp.tools.economics import albion_find_arbitrage_opportunities


async def main():
    quota = albion_get_api_quota_status()
    print(f"Status Inicial de Quota: {quota['aodp_rest_rate_limiter']['health']}")

    # Consulta em lote
    prices = await albion_get_current_prices(
        item_ids=["T4_BAG", "T5_BAG", "T6_BAG"],
        locations=["Lymhurst", "Bridgewatch", "Caerleon", "Black Market"],
        qualities=[1]
    )
    print(f"Total de cotações obtidas: {len(prices['quotes'])}")
    for q in prices['quotes'][:4]:
        print(f"  - [{q['city']}] {q['item_name_pt']} ({q['item_id']}): Venda={q['sell_price_min']} | Compra={q['buy_price_max']}")

    # Arbitragem
    arb = await albion_find_arbitrage_opportunities(
        item_ids=["T4_BAG", "T5_BAG"],
        source_cities=["Lymhurst", "Bridgewatch"],
        target_cities=["Caerleon", "Black Market"],
        min_roi_pct=5.0
    )
    print(f"Oportunidades de arbitragem encontradas: {arb['total_opportunities']}")
    for op in arb['opportunities'][:3]:
        print(f"  * {op['item_name_pt']} ({op['buy_city']} -> {op['sell_city']}): Lucro={op['unit_profit']} (ROI: {op['roi_pct']}%)")

    final_quota = albion_get_api_quota_status()
    print(f"Chamadas restantes no minuto: {final_quota['aodp_rest_rate_limiter']['window_1_minute']['remaining']}")


if __name__ == "__main__":
    asyncio.run(main())
