"""
CLI Runner para Otimização de Builds Econômicas por Tier Equivalente.

Exemplo de uso:
python .agents/skills/albion-investment-wizard/scripts/optimize_build.py --city Lymhurst --tier 7 --items "Machado de Guerra" "Casaco de Mercenário" "Capuz de Assassino" "Botas de Soldado"
"""

import sys
import os
import asyncio
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Garante raiz do repositório no path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.albion_mcp.core.build_optimizer import optimize_budget_build


def parse_args():
    parser = argparse.ArgumentParser(
        description="Otimizador de Custo de Builds por Tier Equivalente (Albion Online)"
    )
    parser.add_argument(
        "--city",
        type=str,
        default="Lymhurst",
        help="Cidade onde os itens serão comprados (ex: Lymhurst, Bridgewatch, Martlock)."
    )
    parser.add_argument(
        "--tier",
        type=int,
        default=7,
        help="Nível de tier equivalente desejado (ex: 6, 7, 8). Padrão: 7."
    )
    parser.add_argument(
        "--items",
        nargs="+",
        default=["Machado de Guerra", "Casaco de Mercenário", "Capuz de Assassino", "Botas de Soldado"],
        help="Lista de itens (nomes em PT-BR, EN ou IDs técnicos)."
    )
    parser.add_argument(
        "--price-mode",
        type=str,
        choices=["live", "history", "databricks"],
        default="live",
        help="Modo de cotação: 'live' (mercado ao vivo), 'history' (SQLite) ou 'databricks'."
    )
    parser.add_argument(
        "--region",
        type=str,
        default="americas",
        help="Servidor do Albion ('americas', 'europe', 'asia'). Padrão: americas."
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    print("\n" + "=" * 70)
    print("⚔️  ALBION ONLINE — OTIMIZADOR DE BUILDS ECONÔMICAS")
    print("=" * 70)
    print(f"📍 Cidade de Compra: {args.city}")
    print(f"🎯 Tier Equivalente Alvo: Tier {args.tier} eq")
    print(f"🌐 Servidor / Modo: {args.region.upper()} | Modo: {args.price_mode.upper()}")
    print(f"🎒 Itens da Build ({len(args.items)}): {', '.join(args.items)}")
    print("=" * 70 + "\n")

    print("🔍 Consultando mercado e gerando combinações equivalentes...")
    res = await optimize_budget_build(
        items=args.items,
        target_tier_equivalent=args.tier,
        city=args.city,
        price_mode=args.price_mode,
        server_region=args.region
    )

    if "error" in res:
        print(f"❌ Erro: {res['error']}")
        if res.get("unresolved_items"):
            print(f"   Itens não resolvidos: {res['unresolved_items']}")
        return

    summary = res["summary"]
    pieces = res["build_pieces"]

    print("\n📋 COMPARAÇÃO POR PEÇA DE EQUIPAMENTO:")
    print("-" * 70)

    for p in pieces:
        rec = p["recommended"]
        flat = p.get("flat_reference")
        stock_badge = "✅ Em estoque" if rec["in_stock"] else "⚠️ Sem oferta direta"
        print(f"\n🏷️  [{p['slot_type']}] {p['base_name_pt']}")
        print(f"    ⭐ Escolha Mais Barata: {rec['tier_enchant']} ({rec['name_pt']})")
        print(f"       Preço: {rec['price']:,} prata ({stock_badge}) | Qualidade: {rec['quality']}")
        if flat and flat.get("price", 0) > 0:
            print(f"       Referência Flat ({flat['tier_enchant']}): {flat['price']:,} prata")
            if rec["savings_vs_flat"] > 0:
                print(f"       💰 Economia neste slot: -{rec['savings_vs_flat']:,} prata ({rec['savings_vs_flat_pct']}%)")
        print("       Opções equivalentes avaliadas:")
        for opt in p["all_equivalent_options"]:
            st = "Disponível" if opt["in_stock"] else "Sem oferta"
            star = " ◀ MELHOR OPÇÃO" if opt["item_id"] == rec["item_id"] else ""
            print(f"         - {opt['tier_enchant']:<4} | Preço: {opt['price']:>10,} prata | {st:<11}{star}")

    print("\n" + "=" * 70)
    print("📊 RESUMO FINANCEIRO DA BUILD COMPLETA:")
    print("=" * 70)
    print(f"💎 Custo Total da Build Otimizada:  {summary['total_optimized_cost']:,} prata")
    print(f"🏛️  Custo Comprando Flat ({args.tier}.0 direto): {summary['total_flat_cost']:,} prata")
    print(f"💰 Economia Total Líquida:         {summary['total_savings_silver']:,} prata (-{summary['total_savings_pct']}%)")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
