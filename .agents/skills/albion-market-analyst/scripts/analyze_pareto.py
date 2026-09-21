#!/usr/bin/env python3
"""
CLI de Análise Macroeconômica & Curva de Pareto — Albion Tools.
Executa análise de Pareto 80/20 de volume diário por cidade, histórico de preços e monitoramento do Ouro.
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

from src.albion_mcp.tools.market_history import albion_get_market_pareto, albion_get_price_history
from src.albion_mcp.tools.market_live import albion_get_gold_prices


async def run_analysis(args):
    if args.gold:
        print("=" * 65)
        print("🪙 COTAÇÃO & HISTÓRICO DO OURO (GOLD INDEX) — ALBION ONLINE")
        print(f"Servidor: {args.region.upper()} | Pontos: {args.gold_points}")
        print("=" * 65)
        res = await albion_get_gold_prices(count=args.gold_points, region=args.region)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return

    if args.history_item:
        print("=" * 65)
        print(f"📊 HISTÓRICO DE PREÇOS E VOLUME DIÁRIO: {args.history_item}")
        print(f"Cidade(s): {args.city or 'Todas'} | Servidor: {args.region.upper()}")
        print("=" * 65)
        cities = [args.city] if args.city else None
        res = await albion_get_price_history(
            item_ids=[args.history_item],
            locations=cities,
            time_scale=24,
            region=args.region
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return

    print("=" * 65)
    print("📈 CURVA DE PARETO 80/20 — MAIORES VOLUMES DO MERCADO")
    print(f"Top: {args.top} itens de maior movimentação em prata diária")
    print("=" * 65)

    res = albion_get_market_pareto(top_n=args.top)
    print(json.dumps(res, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Analista de Mercado & Curva de Pareto")
    parser.add_argument("--top", type=int, default=20, help="Quantidade de itens no topo da curva de Pareto (default: 20)")
    parser.add_argument("--city", type=str, help="Cidade para análise de histórico (ex: Caerleon, Lymhurst)")
    parser.add_argument("--gold", action="store_true", help="Consulta histórico e cotação do Ouro")
    parser.add_argument("--gold-points", type=int, default=24, help="Número de pontos do histórico do ouro (default: 24)")
    parser.add_argument("--history-item", type=str, help="ID do item para análise de histórico diário (ex: T4_BAG)")
    parser.add_argument("--region", type=str, default="americas", choices=["americas", "europe", "asia"], help="Servidor")

    args = parser.parse_args()
    asyncio.run(run_analysis(args))


if __name__ == "__main__":
    main()
