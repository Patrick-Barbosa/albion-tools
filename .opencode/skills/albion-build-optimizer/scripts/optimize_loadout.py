#!/usr/bin/env python3
"""
Otimizador de custo de build por Tier Equivalente — Albion Online.

Exemplo:
    python3 optimize_loadout.py --city Lymhurst --tier 7 \
        --items "Machado de Guerra" "Casaco de Mercenário" "Capuz de Caçador" "Botas de Soldado"
"""

import argparse
import json
import sys
from pathlib import Path

# Skill instalada via `npx skills add`: o núcleo viaja dentro da própria skill.
# No repositório, o núcleo fica na raiz de .opencode/skills (fonte de verdade).
for _base in (Path(__file__).resolve().parents[2], Path(__file__).resolve().parents[1]):
    if (_base / "_albion_core").is_dir():
        sys.path.insert(0, str(_base))
        break

from _albion_core import anti_phantom, builds

DEFAULT_ITEMS = ["Machado de Guerra", "Casaco de Mercenário", "Capuz de Caçador", "Botas de Soldado"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Otimizador de Custo de Builds")
    parser.add_argument("--city", default="Lymhurst", help="Cidade de compra")
    parser.add_argument("--tier", type=int, default=7, help="Tier equivalente alvo (4 a 8)")
    parser.add_argument("--items", nargs="+", default=DEFAULT_ITEMS, help="Itens (PT-BR, EN ou item ID)")
    parser.add_argument("--price-mode", choices=["live", "history"], default="live", help="Fonte de preço")
    parser.add_argument("--region", default="americas", choices=["americas", "europe", "asia"])
    parser.add_argument("--reroll", action="store_true", help="Simula reroll de qualidade do item")
    parser.add_argument("--item-id", default="T6_MAIN_SWORD", help="Item ID para o reroll")
    parser.add_argument("--current-quality", type=int, default=1, choices=[1, 2, 3, 4])
    parser.add_argument("--target-quality", type=int, default=4, choices=[2, 3, 4, 5])
    parser.add_argument("--json", action="store_true", help="Saída apenas em JSON")
    args = parser.parse_args()

    if args.reroll:
        result = anti_phantom.simulate_quality_reroll(args.item_id, args.current_quality, args.target_quality)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

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
    print("=" * 74)
    print(f"🛡️ BUILD T{args.tier} EQUIVALENTE — {args.city}")
    print(
        f"Otimizado: {summary['total_optimized_cost']:,} 🪙 | "
        f"T7 puro: {summary['total_flat_cost']:,} 🪙 | "
        f"Economia: {summary['total_savings_silver']:,} 🪙 ({summary['total_savings_pct']}%)".replace(",", ".")
    )
    print("=" * 74)

    for piece in result["build_pieces"]:
        rec = piece["recommended"]
        print(f"\n[{piece['slot_type']}] {piece['base_name_pt']}")
        print(
            f"  ✅ {rec['tier_enchant']} {rec['name_pt']} — {rec['price']:,} 🪙".replace(",", ".")
            + (f" (economia de {rec['savings_vs_flat']:,} 🪙 vs flat)".replace(",", ".") if rec["savings_vs_flat"] else "")
        )
        for option in piece["all_equivalent_options"]:
            mark = "→" if option["item_id"] == rec["item_id"] else " "
            price = f"{option['price']:,}".replace(",", ".") if option["price"] else "sem ordem"
            print(f"   {mark} {option['tier_enchant']:<4} {option['name_pt'][:38]:<40}{price:>12} 🪙")

    if summary["unresolved_items"]:
        print(f"\n⚠️ Não resolvidos: {', '.join(summary['unresolved_items'])}")

    print("\nJSON completo:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
