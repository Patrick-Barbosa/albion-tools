#!/usr/bin/env python3
"""
Sniper do Mercado Negro de Caerleon — Albion Online.

Cruza as Buy Orders do Black Market com o menor sell order das capitais reais
e calcula a margem líquida (venda direta: apenas 4%/8%, sem setup fee).

Exemplo:
    python3 snipe_black_market.py --items T4_BAG,T5_BAG,T6_MAIN_SWORD --premium --min-margin 20
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Skill instalada via `npx skills add`: o núcleo viaja dentro da própria skill.
# No repositório, o núcleo fica na raiz de .opencode/skills (fonte de verdade).
for _base in (Path(__file__).resolve().parents[2], Path(__file__).resolve().parents[1]):
    if (_base / "_albion_core").is_dir():
        sys.path.insert(0, str(_base))
        break

from _albion_core import market
from _albion_core.calculator import calculate_instant_sell_proceeds
from _albion_core.http import ROYAL_CITIES, aodp
from _albion_core.metadata import metadata_manager


def _age_seconds(date_str: str) -> int | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            parsed = datetime.strptime(date_str.split("+")[0].split("Z")[0], fmt).replace(tzinfo=timezone.utc)
            return int((datetime.now(timezone.utc) - parsed).total_seconds())
        except ValueError:
            continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Sniper de Buy Orders do Mercado Negro")
    parser.add_argument("--items", required=True, help="IDs separados por vírgula (ex: T4_BAG,T5_BAG)")
    parser.add_argument("--min-price", type=int, default=10000, help="Buy order mínima no Black Market")
    parser.add_argument("--min-margin", type=float, default=15.0, help="Margem líquida mínima em %%")
    parser.add_argument("--max-age", type=int, default=86400, help="Idade máxima da cotação em segundos (0 = sem filtro)")
    parser.add_argument("--premium", action="store_true", help="Premium ativo (taxa 4%%)")
    parser.add_argument("--region", default="americas", choices=["americas", "europe", "asia"])
    parser.add_argument("--json", action="store_true", help="Saída apenas em JSON")
    args = parser.parse_args()

    metadata_manager.ensure_data_loaded()
    item_ids = [item.strip() for item in args.items.split(",") if item.strip()]

    rows = aodp.get_prices(item_ids, locations=ROYAL_CITIES + ["Black Market"], qualities=[1], region=args.region)

    bm_orders = {}
    cheapest_royal = {}

    for row in rows:
        item_id = row.get("item_id")
        if row.get("city") == "Black Market":
            price = row.get("buy_price_max") or 0
            if price >= args.min_price:
                bm_orders[item_id] = {
                    "price": price,
                    "date": row.get("buy_price_max_date"),
                    "age": _age_seconds(row.get("buy_price_max_date")),
                }
        elif row.get("city") in ROYAL_CITIES:
            price = row.get("sell_price_min") or 0
            if price > 0 and (item_id not in cheapest_royal or price < cheapest_royal[item_id]["price"]):
                cheapest_royal[item_id] = {"price": price, "city": row.get("city")}

    hits = []
    for item_id, order in bm_orders.items():
        source = cheapest_royal.get(item_id)
        if not source:
            continue
        if order["age"] is not None and args.max_age > 0 and order["age"] > args.max_age:
            continue

        net = calculate_instant_sell_proceeds(order["price"], has_premium=args.premium)
        profit = net - source["price"]
        margin = round(profit / source["price"] * 100, 1) if source["price"] else 0.0
        if margin < args.min_margin:
            continue

        hits.append(
            {
                "item_id": item_id,
                "item_name_pt": metadata_manager.get_item_name(item_id),
                "buy_city": source["city"],
                "buy_price": source["price"],
                "black_market_price": order["price"],
                "net_revenue": net,
                "unit_profit": profit,
                "margin_pct": margin,
                "quote_age_seconds": order["age"],
            }
        )

    hits.sort(key=lambda row: row["unit_profit"], reverse=True)
    result = {
        "black_market": "Caerleon",
        "items_scanned": len(item_ids),
        "matches": len(hits),
        "min_margin_filter": args.min_margin,
        "has_premium": args.premium,
        "opportunities": hits,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 70)
    print("🕶️ BLACK MARKET SNIPER — CAERLEON")
    print(f"Itens: {len(item_ids)} | Margem mínima: {args.min_margin}% | Premium: {'sim' if args.premium else 'não'}")
    print("=" * 70)

    if not hits:
        print("\nNenhuma Buy Order acima do filtro. O Black Market seca rápido: reduza --min-margin.")
        return 0

    print(f"\n{'Item':<36}{'Compra':>18}{'BM':>12}{'Lucro':>11}{'Margem':>9}")
    print("-" * 86)
    for row in hits:
        buy = f"{row['buy_city']} {row['buy_price']:,}".replace(",", ".")
        print(
            f"{row['item_name_pt'][:32]:<36}{buy:>18}"
            f"{row['black_market_price']:>12,}{row['unit_profit']:>11,}{row['margin_pct']:>8}%"
        )

    print("\n⚠️ Travessia de Zona Vermelha: use montaria rápida e nunca carregue mais que 1 fardo por viagem.")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
