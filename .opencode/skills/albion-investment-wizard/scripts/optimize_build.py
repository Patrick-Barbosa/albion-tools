#!/usr/bin/env python3
"""
Otimizador de build por Tier Equivalente (versão do Investment Wizard).

Exemplo:
    python3 optimize_build.py --city Lymhurst --tier 7 \
        --items "Machado de Guerra" "Casaco de Mercenário" "Capuz de Assassino" "Botas de Soldado"
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from _albion_core import builds

DEFAULT_ITEMS = ["Machado de Guerra", "Casaco de Mercenário", "Capuz de Assassino", "Botas de Soldado"]


def parse_args():
    parser = argparse.ArgumentParser(description="Otimizador de Custo de Builds por Tier Equivalente")
    parser.add_argument("--city", default="Lymhurst", help="Cidade onde os itens serão comprados")
    parser.add_argument("--tier", type=int, default=7, help="Tier equivalente desejado (4 a 8)")
    parser.add_argument("--items", nargs="+", default=DEFAULT_ITEMS, help="Itens (PT-BR, EN ou ID)")
    parser.add_argument("--price-mode", choices=["live", "history"], default="live", help="Fonte de preço")
    parser.add_argument("--region", default="americas", choices=["americas", "europe", "asia"])
    parser.add_argument("--json", action="store_true", help="Saída apenas em JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = builds.optimize_budget_build(
        items=args.items,
        target_tier_equivalent=args.tier,
        city=args.city,
        price_mode=args.price_mode,
        server_region=args.region,
    )

    if args.json or "error" in result:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if "error" not in result else 1

    summary = result["summary"]
    print("=" * 70)
    print(f"🛡️ BUILD T{args.tier} EQUIVALENTE — {args.city}")
    print(
        f"Otimizado: {summary['total_optimized_cost']:,} 🪙 | "
        f"Flat: {summary['total_flat_cost']:,} 🪙 | "
        f"Economia: {summary['total_savings_silver']:,} 🪙 ({summary['total_savings_pct']}%)".replace(",", ".")
    )
    print("=" * 70)

    for piece in result["build_pieces"]:
        rec = piece["recommended"]
        print(f"\n[{piece['slot_type']}] {piece['base_name_pt']}")
        print(f"  ✅ {rec['tier_enchant']} {rec['name_pt']} — {rec['price']:,} 🪙".replace(",", "."))
        for option in piece["all_equivalent_options"]:
            mark = "→" if option["item_id"] == rec["item_id"] else " "
            price = f"{option['price']:,}".replace(",", ".") if option["price"] else "sem ordem"
            print(f"   {mark} {option['tier_enchant']:<4} {option['name_pt'][:38]:<40}{price:>12} 🪙")

    print("\nJSON completo:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
