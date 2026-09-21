#!/usr/bin/env python3
"""
CLI de Scanner de Arbitragem Intercidades — Albion Tools.
Localiza rotas comerciais lucrativas entre cidades reais ou Black Market, considerando taxas de mercado.
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

from src.albion_mcp.tools.economics import albion_find_arbitrage_opportunities


async def run_scan(args):
    source_cities = [args.origin] if args.origin else ["Bridgewatch", "Lymhurst", "Fort Sterling", "Martlock", "Thetford"]
    if args.safe_only:
        target_cities = ["Bridgewatch", "Lymhurst", "Fort Sterling", "Martlock", "Thetford"]
    elif args.destination:
        target_cities = [args.destination]
    else:
        target_cities = ["Caerleon", "Black Market", "Bridgewatch", "Lymhurst", "Fort Sterling", "Martlock", "Thetford"]

    items = args.items.split(",") if args.items else [
        "T4_BAG", "T5_BAG", "T6_BAG",
        "T4_CAPE", "T5_CAPE", "T6_CAPE",
        "T4_ARMOR_PLATE_SET1", "T5_ARMOR_PLATE_SET1",
        "T4_MAIN_SWORD", "T5_MAIN_SWORD",
        "T4_MAIN_AXE", "T5_MAIN_AXE"
    ]

    print("=" * 65)
    print("🚚 SCANNER DE ARBITRAGEM & ROTAS COMERCIAIS — ALBION ONLINE")
    print(f"Origem(ns): {', '.join(source_cities)} | Destino(s): {', '.join(target_cities)}")
    print(f"Itens monitorados: {len(items)} | ROI Mínimo: {args.min_roi}% | Premium: {args.premium}")
    print("=" * 65)

    res = await albion_find_arbitrage_opportunities(
        item_ids=items,
        source_cities=source_cities,
        target_cities=target_cities,
        min_roi_pct=args.min_roi,
        has_premium=args.premium,
        region=args.region
    )

    print(json.dumps(res, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Scanner de Arbitragem Intercidades")
    parser.add_argument("--origin", type=str, help="Cidade de compra (ex: Thetford)")
    parser.add_argument("--destination", type=str, help="Cidade de venda (ex: Martlock)")
    parser.add_argument("--items", type=str, help="Lista de itens separados por vírgula (ex: T4_BAG,T5_BAG)")
    parser.add_argument("--min-roi", type=float, default=12.0, help="ROI mínimo percentual (default: 12.0%%)")
    parser.add_argument("--safe-only", action="store_true", help="Filtra apenas capitais seguras (sem Black Market/Caerleon)")
    parser.add_argument("--premium", action="store_true", help="Se ativado, utiliza 4%% de taxa de venda (senão 8%%)")
    parser.add_argument("--region", type=str, default="americas", choices=["americas", "europe", "asia"], help="Servidor/Região")

    args = parser.parse_args()
    asyncio.run(run_scan(args))


if __name__ == "__main__":
    main()
