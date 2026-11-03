#!/usr/bin/env python3
"""
Analista macroeconômico: Curva de Pareto 80/20, histórico e ouro · Albion Online.

Exemplos:
    python3 analyze_pareto.py --category "Recursos Refinados" --top 20
    python3 analyze_pareto.py --gold
    python3 analyze_pareto.py --history-item T4_BAG --city Caerleon
"""

import argparse
import json
import sys
from pathlib import Path

# Skill instalada via `npx skills add`: o núcleo viaja dentro da própria skill.
# No repositório, o núcleo fica na raiz de skills (fonte de verdade).
for _base in (Path(__file__).resolve().parents[2], Path(__file__).resolve().parents[1]):
    if (_base / "_albion_core").is_dir():
        sys.path.insert(0, str(_base))
        break

from _albion_core import market, pareto


def _money(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analista de Mercado & Curva de Pareto")
    parser.add_argument("--top", type=int, default=20, help="Itens exibidos no topo da curva")
    parser.add_argument("--city", help="Cidade (padrão: todas as capitais reais)")
    parser.add_argument("--category", help="Categoria do catálogo (ex: 'Recursos Refinados')")
    parser.add_argument("--tier", help="Filtro de tier (ex: T5)")
    parser.add_argument("--items", help="IDs separados por vírgula (sobrepõe categoria/tier)")
    parser.add_argument("--days", type=int, default=7, help="Janela histórica em dias")
    parser.add_argument("--max-items", type=int, default=120, help="Teto de itens varridos")
    parser.add_argument("--gold", action="store_true", help="Consulta a cotação do ouro")
    parser.add_argument("--gold-points", type=int, default=24, help="Pontos do histórico de ouro")
    parser.add_argument("--history-item", help="Item ID para histórico diário (ex: T4_BAG)")
    parser.add_argument("--region", default="americas", choices=["americas", "europe", "asia"])
    parser.add_argument("--json", action="store_true", help="Saída apenas em JSON")
    args = parser.parse_args()

    output = {}

    if args.gold:
        output["gold"] = market.gold_prices(args.gold_points, args.region)

    if args.history_item:
        output["history"] = market.price_history(
            [args.history_item], locations=[args.city] if args.city else None, days=args.days, region=args.region
        )

    if not args.gold and not args.history_item:
        item_ids = [item.strip() for item in args.items.split(",")] if args.items else None
        output["pareto"] = pareto.pareto_analysis(
            item_ids=item_ids,
            category=args.category,
            tier=args.tier,
            city=args.city,
            days=args.days,
            top_n=args.top,
            region=args.region,
            max_items=args.max_items,
        )

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return 0

    if "gold" in output:
        gold = output["gold"]
        print("=" * 60)
        print("🪙 OURO · ALBION ONLINE")
        print("=" * 60)
        if gold["count"]:
            print(f"Última cotação: {_money(gold['latest_price'])} 🪙 por ouro")
            print(f"Média: {_money(gold['avg_price'])} | Mín: {_money(gold['min_price'])} | Máx: {_money(gold['max_price'])}")
        else:
            print("Sem dados de ouro no momento.")

    if "history" in output:
        print("\n" + "=" * 60)
        print("📈 HISTÓRICO DIÁRIO")
        print("=" * 60)
        for row in output["history"].get("items", []):
            print(
                f"{row['item_name_pt']} @ {row['city']}: média {_money(row['avg_price'])} 🪙 | "
                f"{row['avg_daily_sales']} vendas/dia | {row['total_sold']} unidades em {row['window_days']}d"
            )

    if "pareto" in output:
        data = output["pareto"]
        if "error" in data:
            print(data["error"])
            return 1
        universe = data["universe"]
        print("=" * 78)
        print("📊 CURVA DE PARETO 80/20 · PRATA DIÁRIA")
        print("=" * 78)
        print(
            f"Universo: {universe['category'] or universe['tier'] or 'personalizado'} | "
            f"{universe['items_with_data']}/{universe['items_scanned']} itens com dados | "
            f"{universe['city']} | {universe['window_days']}d"
        )
        print(f"Prata diária total: {_money(data['total_market_daily_silver'])} 🪙")
        p80 = data["pareto_80"]
        print(f"80% da prata vem de {p80['items_needed']} itens ({p80['share_of_universe_pct']}% do universo)\n")
        print(f"{'#':<4}{'Item':<40}{'Prata/dia':>14}{'Share':>9}{'Acum.':>9}")
        print("-" * 78)
        for index, row in enumerate(data["items"], start=1):
            print(
                f"{index:<4}{row['item_name_pt'][:36]:<40}"
                f"{_money(row['daily_silver']):>14}{row['share_pct']:>8}%{row['cum_share_pct']:>8}%"
            )

    print("\nJSON completo:")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
