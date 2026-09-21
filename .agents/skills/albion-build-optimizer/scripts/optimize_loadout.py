#!/usr/bin/env python3
"""
CLI de Otimização de Builds e Custo de Equipamentos — Albion Tools.
Calcula a combinação de menor custo por slot para atingir o Tier Equivalente (ex: 4.3, 5.2, 6.1 vs 7.0)
e avalia a probabilidade e custo esperado de reroll de qualidade.
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

from src.albion_mcp.core.build_optimizer import optimize_budget_build
from src.albion_mcp.tools.anti_hallucination import albion_simulate_quality_reroll


async def run_optimizer(args):
    if args.reroll:
        print("=" * 65)
        print("🎲 SIMULADOR DE REROLL DE QUALIDADE (BANCADA DE REPARO)")
        print(f"Item: {args.item_id or 'T6_MAIN_SWORD'} | Qualidade Atual: Q{args.current_quality} -> Alvo: Q{args.target_quality}")
        print("=" * 65)
        res = albion_simulate_quality_reroll(
            item_id=args.item_id or "T6_MAIN_SWORD",
            current_quality=args.current_quality,
            target_quality=args.target_quality
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return

    print("=" * 70)
    print("⚔️  ALBION ONLINE — OTIMIZADOR DE BUILDS ECONÔMICAS")
    print(f"📍 Cidade: {args.city} | 🎯 Tier Equivalente: T{args.tier} | 🌐 Servidor: {args.region.upper()}")
    print(f"🎒 Itens: {', '.join(args.items)}")
    print("=" * 70)

    res = await optimize_budget_build(
        items=args.items,
        target_tier_equivalent=args.tier,
        city=args.city,
        price_mode=args.price_mode,
        server_region=args.region
    )

    if "error" in res:
        print(f"❌ Erro: {res['error']}")
        return

    summary = res.get("summary", {})
    pieces = res.get("build_pieces", [])

    print("\n📋 COMPARAÇÃO POR PEÇA DE EQUIPAMENTO:")
    print("-" * 70)
    for p in pieces:
        rec = p["recommended"]
        flat = p.get("flat_reference")
        flat_cost = flat["best_buy_cost"] if flat else 0
        diff = flat_cost - rec["best_buy_cost"]
        pct = round((diff / flat_cost * 100), 1) if flat_cost > 0 else 0.0
        print(f"• [{p['slot_type']}] {p['base_name_pt']}:")
        print(f"   🏆 Recomendado: {rec['tier_enchant']} ({rec['name_pt']}) -> {rec['best_buy_cost']:,} prata")
        if flat:
            print(f"   📊 Flat {flat['tier_enchant']}: {flat_cost:,} prata (Economia: {diff:,} prata / {pct}%)")

    print("\n" + "=" * 70)
    print(f"💰 CUSTO TOTAL OTIMIZADO: {summary.get('optimized_total_cost', 0):,} prata")
    print(f"🏷️  CUSTO FLAT COMPARATIVO: {summary.get('flat_total_cost', 0):,} prata")
    print(f"🎉 ECONOMIA TOTAL: {summary.get('total_savings_silver', 0):,} prata ({summary.get('total_savings_pct', 0.0)}%)")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Otimizador de Custo de Builds Albion Online")
    parser.add_argument("--city", type=str, default="Lymhurst", help="Cidade de compra")
    parser.add_argument("--tier", type=int, default=7, help="Tier equivalente alvo (ex: 6, 7, 8)")
    parser.add_argument("--items", nargs="+", default=["Machado de Guerra", "Casaco de Mercenário", "Capuz de Caçador", "Botas de Soldado"], help="Lista de itens")
    parser.add_argument("--price-mode", type=str, choices=["live", "history", "databricks"], default="live", help="Modo de cotação")
    parser.add_argument("--region", type=str, default="americas", choices=["americas", "europe", "asia"], help="Servidor")

    # Opções para teste de Reroll
    parser.add_argument("--reroll", action="store_true", help="Executa simulação de reroll de qualidade")
    parser.add_argument("--item-id", type=str, default="T6_MAIN_SWORD", help="Item ID para reroll")
    parser.add_argument("--current-quality", type=int, default=1, choices=[1, 2, 3, 4], help="Qualidade inicial (1=Normal, 2=Bom, 3=Notável, 4=Excelente)")
    parser.add_argument("--target-quality", type=int, default=4, choices=[2, 3, 4, 5], help="Qualidade alvo (2=Bom, 3=Notável, 4=Excelente, 5=Obra-prima)")

    args = parser.parse_args()
    asyncio.run(run_optimizer(args))


if __name__ == "__main__":
    main()
