#!/usr/bin/env python3
"""
Wizard de Investimentos — Albion Online.

Varre um universo de itens, encontra arbitragens acima do ROI mínimo e aloca o
orçamento em uma carteira inteira (knapsack), reservando o setup fee.

Exemplo:
    python3 run_wizard.py --budget 5000000 --city Lymhurst --dest "Black Market" --premium
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

from _albion_core import anti_phantom, economics, items as items_core, market
from _albion_core.http import ROYAL_CITIES


def _money(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")


def main() -> int:
    parser = argparse.ArgumentParser(description="Wizard de Investimentos Albion")
    parser.add_argument("--budget", type=int, default=5_000_000, help="Orçamento em prata")
    parser.add_argument("--city", default="Lymhurst", help="Cidade de operação/compra")
    parser.add_argument("--dest", help="Mercado de destino (ex: 'Black Market', 'Caerleon', 'Martlock')")
    parser.add_argument("--category", default="Recursos Refinados", help="Categoria varrida")
    parser.add_argument("--tier", help="Filtro de tier (ex: T5)")
    parser.add_argument("--max-items", type=int, default=60, help="Teto de itens varridos")
    parser.add_argument("--min-roi", type=float, default=15.0, help="ROI mínimo por item")
    parser.add_argument("--premium", action="store_true", help="Premium ativo (taxa 4%%)")
    parser.add_argument("--max-positions", type=int, default=5, help="Máximo de itens na carteira")
    parser.add_argument("--region", default="americas", choices=["americas", "europe", "asia"])
    parser.add_argument("--json", action="store_true", help="Saída apenas em JSON")
    args = parser.parse_args()

    universe = items_core.resolve_universe(category=args.category, tier=args.tier, limit=args.max_items)
    if not universe:
        print("Universo vazio: ajuste --category/--tier.", file=sys.stderr)
        return 1

    targets = [args.dest] if args.dest else ROYAL_CITIES + ["Black Market"]
    scan = economics.find_arbitrage(
        item_ids=universe,
        source_cities=[args.city],
        target_cities=targets,
        min_roi_pct=args.min_roi,
        has_premium=args.premium,
        region=args.region,
        qualities=[1],
    )

    opportunities = scan.get("opportunities", [])
    volumes = {}
    if opportunities:
        history = market.price_history(
            [row["item_id"] for row in opportunities],
            locations=[args.city],
            days=7,
            region=args.region,
        )
        volumes = {row["item_id"]: row["avg_daily_sales"] for row in history.get("items", [])}

    candidates = [
        {
            "item_id": row["item_id"],
            "item_name": row["item_name_pt"],
            "buy_price": row["buy_price"],
            "sell_price": row["sell_price"],
            "daily_volume": volumes.get(row["item_id"], 0) or None,
            "is_buy_order": False,
            "is_sell_order": not row["is_black_market"],
        }
        for row in opportunities
    ]

    portfolio = anti_phantom.allocate_budget(
        budget=args.budget,
        candidate_items=candidates,
        max_items_count=args.max_positions,
        has_premium=args.premium,
    )

    result = {
        "parameters": {
            "budget": args.budget,
            "city": args.city,
            "destination": args.dest or "melhor destino",
            "category": args.category,
            "premium": args.premium,
            "min_roi": args.min_roi,
        },
        "opportunities_found": len(candidates),
        "portfolio": portfolio,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 70)
    print("🧙 WIZARD DE INVESTIMENTOS — ALBION ONLINE")
    print("=" * 70)
    print(
        f"Orçamento: {_money(args.budget)} 🪙 | Origem: {args.city} | "
        f"Destino: {args.dest or 'melhor'} | Premium: {'sim' if args.premium else 'não'}"
    )
    print(f"Universo: {len(universe)} itens ({args.category}) | ROI mínimo: {args.min_roi}%")

    if not candidates:
        print("\nNenhuma oportunidade acima do ROI mínimo. Reduza --min-roi ou troque de categoria.")
        return 0

    print(f"\nOportunidades encontradas: {len(candidates)}\n")

    allocations = portfolio.get("allocations") or portfolio.get("items") or []
    if allocations:
        print(f"{'Item':<34}{'Qtd':>8}{'Capital':>14}{'Lucro est.':>14}")
        print("-" * 70)
        for row in allocations:
            name = row.get("item_name") or row.get("item_id", "")
            qty = row.get("quantity_integer", 0)
            capital = row.get("total_silver_invested", 0)
            profit = row.get("projected_net_profit", 0)
            print(f"{name[:30]:<34}{qty:>8}{_money(capital):>14}{_money(profit):>14}")

    print("\nResumo:")
    print(json.dumps(portfolio.get("summary", portfolio), indent=2, ensure_ascii=False))
    print("\nJSON completo:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
