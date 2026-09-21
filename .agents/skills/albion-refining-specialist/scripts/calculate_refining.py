#!/usr/bin/env python3
"""
CLI de Simulação de Refino Industrial & Cascata — Albion Tools.
Executa simulações econômicas respeitando RRR (40% base / 53.9% foco), taxas de bancas e retorno líquido.
"""

import os
import sys
import argparse
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Garante acesso aos módulos do projeto
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.albion_mcp.tools.economics import albion_calculate_refining, albion_calculate_cascade_refining


def main():
    parser = argparse.ArgumentParser(description="Simulador de Refino Industrial Albion Online")
    parser.add_argument("--resource", type=str, default="ORE", choices=["ORE", "WOOD", "FIBER", "HIDE", "ROCK"], help="Tipo de recurso")
    parser.add_argument("--tier", type=int, default=5, choices=range(2, 9), help="Tier do item (2 a 8)")
    parser.add_argument("--enchant", type=int, default=0, choices=range(0, 5), help="Encantamento (.0 a .4)")
    parser.add_argument("--station-fee", type=int, default=500, help="Taxa da estação por 100 nutrição (ex: 500)")
    parser.add_argument("--focus", action="store_true", help="Se ativado, utiliza Foco de Artesanato (53.9% RRR)")
    parser.add_argument("--premium", action="store_true", help="Se ativado, aplica 4% de taxa de venda (senão 8%)")
    parser.add_argument("--cascade", action="store_true", help="Executa simulação de refino em cascata ponta a ponta")
    parser.add_argument("--budget", type=int, default=2000000, help="Orçamento para cascata (default: 2M prata)")

    args = parser.parse_args()

    print("=" * 60)
    print("🏭 SIMULADOR DE REFINO INDUSTRIAL — ALBION ONLINE")
    print(f"Recurso: {args.resource} | Tier: T{args.tier}.{args.enchant} | Foco: {args.focus} | Premium: {args.premium}")
    print("=" * 60)

    if args.cascade:
        res = albion_calculate_cascade_refining(
            resource_type=args.resource,
            target_tier=args.tier,
            target_enchantment=args.enchant,
            budget=args.budget,
            has_focus=args.focus,
            has_premium=args.premium,
            station_fee_per_100=args.station_fee
        )
    else:
        res = albion_calculate_refining(
            resource_type=args.resource,
            tier=args.tier,
            enchantment=args.enchant,
            has_focus=args.focus,
            has_premium=args.premium,
            station_fee_per_100=args.station_fee
        )

    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
