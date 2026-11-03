#!/usr/bin/env python3
"""
Simulador de refino industrial e cascata de sobras — Albion Online.

Exemplo:
    python3 calculate_refining.py --resource ORE --tier 5 --premium
    python3 calculate_refining.py --resource WOOD --tier 6 --focus --premium --cascade --budget 5000000
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

from _albion_core import refining


def _money(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulador de Refino Industrial")
    parser.add_argument("--resource", default="ORE", choices=["ORE", "WOOD", "FIBER", "HIDE", "ROCK"])
    parser.add_argument("--tier", type=int, default=5, choices=range(2, 9))
    parser.add_argument("--enchant", type=int, default=0, choices=range(0, 5))
    parser.add_argument("--station-fee", type=int, default=500, help="Taxa da estação por 100 de nutrição")
    parser.add_argument("--focus", action="store_true", help="Usa Foco de Artesanato (RRR 53.9%%)")
    parser.add_argument("--premium", action="store_true", help="Premium ativo (taxa 4%%)")
    parser.add_argument("--cascade", action="store_true", help="Simula a cascata completa até o orçamento")
    parser.add_argument("--budget", type=int, default=2_000_000, help="Orçamento da cascata")
    parser.add_argument("--region", default="americas", choices=["americas", "europe", "asia"])
    parser.add_argument("--json", action="store_true", help="Saída apenas em JSON")
    args = parser.parse_args()

    if args.cascade:
        result = refining.calculate_cascade_refining(
            resource_type=args.resource,
            target_tier=args.tier,
            target_enchantment=args.enchant,
            budget=args.budget,
            has_focus=args.focus,
            has_premium=args.premium,
            station_fee_per_100=args.station_fee,
            region=args.region,
        )
    else:
        result = refining.calculate_refining(
            resource_type=args.resource,
            tier=args.tier,
            enchantment=args.enchant,
            has_focus=args.focus,
            has_premium=args.premium,
            station_fee_per_100=args.station_fee,
            region=args.region,
        )

    if args.json or "error" in result:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if "error" not in result else 1

    if args.cascade:
        print("=" * 68)
        print(f"🏭 CASCATA DE REFINO — {result['target_tier']} em {result['refining_city']}")
        print("=" * 68)
        print(f"Orçamento:        {_money(result['budget_silver'])} 🪙")
        print(f"Unidades:         {_money(result['units_produced'])}")
        print(f"Investimento:     {_money(result['total_invested'])} 🪙")
        print(f"Receita líquida:  {_money(result['net_revenue'])} 🪙")
        print(f"Lucro líquido:    {_money(result['net_profit'])} 🪙  (ROI {result['roi_pct']}%)")
        cargo = result["cargo"]
        print(
            f"Carga:            {cargo['total_weight_kg']} kg → {cargo['recommended_mount']} "
            f"(uso {cargo['usage_pct']}%)"
        )
        print(f"Bolsa/Torta:      {cargo['recommended_bag']} / {cargo['recommended_food']}")
    else:
        econ = result["economics"]
        print("=" * 68)
        print(f"🏭 REFINO {result['tier']} — {result['specialized_city']}")
        print("=" * 68)
        raw = result["raw_material"]
        print(f"Insumo bruto:     {raw['quantity']}x {raw['name']} @ {_money(raw['price'])} 🪙 ({raw['price_city']})")
        if result.get("previous_refined_material"):
            prev = result["previous_refined_material"]
            print(f"Barra anterior:   1x {prev['name']} @ {_money(prev['price'])} 🪙")
        product = result["refined_product"]
        print(f"Produto:          {product['name']} vendido a {_money(product['sell_price'])} 🪙")
        print(f"RRR aplicado:     {econ['rrr_pct']}% (foco: {'sim' if econ['has_focus'] else 'não'})")
        print(f"Custo efetivo:    {_money(econ['effective_craft_cost'])} 🪙")
        print(f"Receita líquida:  {_money(product['net_revenue'])} 🪙")
        print(f"Lucro por barra:  {_money(econ['net_profit_per_unit'])} 🪙  (ROI {econ['roi_pct']}%)")
        print(f"Veredito:         {econ['verdict']}")

    print("\nJSON completo:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
