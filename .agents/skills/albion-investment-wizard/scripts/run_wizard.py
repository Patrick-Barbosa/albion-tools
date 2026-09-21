"""
Script auxiliar para o Albion Investment Wizard.
Permite consultar oportunidades de encantamento e flip em tempo real com filtros customizados de orçamento, cidade, premium e estratégia.
"""

import sys
import os
import argparse
import json

sys.stdout.reconfigure(encoding='utf-8')

# Adicionar root do projeto ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))

from backend.metadata import metadata_manager
from backend.buy_order_engine import generate_wizard_portfolio

def run_wizard(budget: int, city: str, is_premium: bool, dest_market: str = "Lymhurst", strategy: str = "fast", min_daily_sales: float = 0.5):
    metadata_manager.ensure_data_loaded()
    
    print(f"=== 🧙‍♂️ WIZARD DE INVESTIMENTOS ALBION ===")
    print(f"📍 Origem: {city} | 🎯 Destino: {dest_market} | 💰 Orçamento: {budget:,}s | 👑 Premium: {'SIM (4% taxa)' if is_premium else 'NÃO (8% taxa)'} | ⚡ Estratégia: {strategy}\n")

    res = generate_wizard_portfolio(
        budget=budget,
        city=city,
        dest_market=dest_market,
        has_premium=is_premium,
        strategy=strategy,
        min_daily_sales=min_daily_sales
    )

    port = res.get("portfolio", {})
    items = port.get("items", [])

    print("=" * 60)
    print(f"💼 CARTEIRA SELECIONADA: {port.get('tag', 'Carteira')} ({port.get('description', '')})")
    print(f"Investimento Total: {port.get('total_investment', 0):,}s")
    print(f"Lucro Líquido Projetado: {port.get('total_net_profit', 0):,}s")
    print(f"ROI Médio Ponderado: {port.get('weighted_roi', 0):.1f}%")
    print(f"Total de Peças: {port.get('total_pieces', 0)}")
    print("-" * 60)
    
    if not items:
        print("⚠️ Nenhum item atendeu aos critérios para a carteira selecionada no momento.")
    else:
        print("Itens Recomendados na Carteira:")
        for item in items:
            name = item.get("item_name") or item.get("base_item_id")
            tier = str(item.get("tier", ""))
            f_ench = item.get("from_level", 0)
            t_ench = item.get("target_enchantment", 1)
            q_name = item.get("quality_name", "Normal")
            pieces = item.get("pieces", 1)
            unit_inv = item.get("unit_investment", 0)
            unit_prof = item.get("net_profit", 0)
            roi = item.get("roi_percent", 0.0)
            base_bid = item.get("base_buy_price", 0)
            sell_price = item.get("sell_price", 0)
            
            print(f"  • {name} (T{tier[1:] if tier.startswith('T') else tier}.{f_ench} -> .{t_ench}) [{q_name}] x{pieces} un")
            print(f"    Ordem de Compra Base: {base_bid:,}s | Venda Estimada: {sell_price:,}s")
            print(f"    Investimento Unit: {unit_inv:,}s | Lucro Líquido Unit: +{unit_prof:,}s (ROI: {roi:.1f}%)")
            
            mats = item.get("material_costs", {})
            mats_str = []
            for m_k, m_v in mats.items():
                mats_str.append(f"{m_v['name']}: {m_v['bid']:,}s (Total: {m_v['total']:,}s)")
            if mats_str:
                print(f"    Insumos: {' | '.join(mats_str)}")
            print()

    print("=" * 60)
    print("🌟 OUTRAS ESTRATÉGIAS DISPONÍVEIS:")
    for s in res.get("available_strategies", []):
        print(f"  • [{s['key'].upper()}] {s['tag']} -> Invest: {s['total_investment']:,}s | Lucro: +{s['total_net_profit']:,}s | ROI: {s['weighted_roi']:.1f}% | Peças: {s['total_pieces']}")

    print("\n🔍 TOP CANDIDATOS GERAIS PARA INSPEÇÃO (FEEDER GATE):")
    candidates = res.get("all_candidates", [])[:8]
    for c in candidates:
        c_name = c.get("item_name") or c.get("base_item_id")
        c_tier = str(c.get("tier", ""))
        print(f"  - [{c.get('base_item_id')}] {c_name} (T{c_tier[1:] if c_tier.startswith('T') else c_tier}.{c.get('from_level')} -> .{c.get('target_enchantment')}) Q{c.get('quality')} | Bid: {c.get('base_buy_price', 0):,}s | Venda: {c.get('sell_price', 0):,}s | Lucro: +{c.get('net_profit', 0):,}s (ROI: {c.get('roi_percent', 0):.1f}%) | Vendas/dia: {c.get('avg_daily_sales', 0):.1f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wizard de Investimentos Albion")
    parser.add_argument("--budget", type=int, default=5000000, help="Orçamento em prata")
    parser.add_argument("--city", type=str, default="Lymhurst", help="Cidade de operação")
    parser.add_argument("--dest", type=str, default="Lymhurst", help="Mercado de destino (ex: Lymhurst ou 'Black Market')")
    parser.add_argument("--premium", action="store_true", help="Conta com Premium (4%% taxa)")
    parser.add_argument("--strategy", type=str, default="fast", choices=["fast", "profit", "balanced"], help="Estratégia")
    parser.add_argument("--min_daily_sales", type=float, default=0.5, help="Vendas diárias mínimas")
    args = parser.parse_args()

    run_wizard(args.budget, args.city, args.premium, args.dest, args.strategy, args.min_daily_sales)
