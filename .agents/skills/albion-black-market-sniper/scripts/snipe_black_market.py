#!/usr/bin/env python3
"""
CLI de Sniper do Mercado Negro (Caerleon) — Albion Tools.
Monitora em tempo real via NATS streaming e AODP as ordens de compra de equipamentos no Black Market.
"""

import os
import sys
import asyncio
import argparse
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.albion_mcp.tools.market_live import albion_nats_get_live_orders
from src.albion_mcp.core.aodp_client import aodp_client
from src.albion_mcp.core.calculator import calculate_instant_sell_proceeds
from src.albion_mcp.core.metadata import metadata_manager


async def fetch_black_market_aodp(items, region, has_premium):
    """Fallback via AODP REST se o buffer NATS estiver vazio na inicialização."""
    quotes = await aodp_client.get_current_prices(item_ids=items, locations=["Black Market"], region=region)
    results = []
    for q in quotes:
        buy_max = q.get("buy_price_max", 0)
        if buy_max > 0:
            net_revenue = calculate_instant_sell_proceeds(buy_max, has_premium=has_premium)
            results.append({
                "item_id": q.get("item_id"),
                "name_pt": metadata_manager.get_item_name(q.get("item_id")),
                "quality": q.get("quality"),
                "black_market_buy_price": buy_max,
                "net_proceeds": net_revenue,
                "date": q.get("buy_price_max_date")
            })
    return results


def main():
    parser = argparse.ArgumentParser(description="Sniper de Ordens do Mercado Negro (Caerleon)")
    parser.add_argument("--items", type=str, help="IDs de itens separados por vírgula (ex: T4_BAG,T5_BAG,T4_MAIN_SWORD)")
    parser.add_argument("--max-age", type=int, default=600, help="Idade máxima em segundos para NATS (default: 600s)")
    parser.add_argument("--min-price", type=int, default=10000, help="Preço mínimo de compra (default: 10.000 prata)")
    parser.add_argument("--premium", action="store_true", help="Se ativado, utiliza 4%% de taxa de venda (senão 8%%)")
    parser.add_argument("--region", type=str, default="americas", choices=["americas", "europe", "asia"], help="Servidor")

    args = parser.parse_args()

    item_filter = args.items.split(",") if args.items else None

    print("=" * 65)
    print("🏴‍☠️ SNIPER DO MERCADO NEGRO (CAERLEON) — ALBION ONLINE")
    print(f"Região: {args.region} | Premium: {args.premium} | Preço Mínimo: {args.min_price:,} prata")
    print("=" * 65)

    # 1. Consulta NATS em memória (Zero custo de cota)
    nats_res = albion_nats_get_live_orders(
        item_ids=item_filter,
        cities=["Black Market"],
        max_age_seconds=args.max_age,
        only_black_market_requests=True
    )

    orders = nats_res.get("orders", [])
    filtered_orders = [o for o in orders if o.get("unit_price", 0) >= args.min_price]

    if filtered_orders:
        print(f"\n⚡ {len(filtered_orders)} Ordens ao Vivo via NATS Firehose (< {args.max_age}s):")
        print(json.dumps(filtered_orders[:20], indent=2, ensure_ascii=False))
    else:
        print("\nℹ️ Nenhuma ordem recente no buffer NATS local. Consultando AODP REST...")
        default_items = item_filter or [
            "T4_BAG", "T5_BAG", "T6_BAG",
            "T4_ARMOR_PLATE_SET1", "T5_ARMOR_PLATE_SET1", "T6_ARMOR_PLATE_SET1",
            "T4_MAIN_SWORD", "T5_MAIN_SWORD", "T6_MAIN_SWORD",
            "T4_MAIN_AXE", "T5_MAIN_AXE", "T6_MAIN_AXE",
            "T4_HEAD_PLATE_SET1", "T5_HEAD_PLATE_SET1"
        ]
        aodp_orders = asyncio.run(fetch_black_market_aodp(default_items, args.region, args.premium))
        aodp_filtered = [o for o in aodp_orders if o.get("black_market_buy_price", 0) >= args.min_price]
        print(f"\n📦 {len(aodp_filtered)} Ordens do Black Market via AODP:")
        print(json.dumps(aodp_filtered[:20], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
