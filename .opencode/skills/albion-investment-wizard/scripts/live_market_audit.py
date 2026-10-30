#!/usr/bin/env python3
"""
Auditoria de frescor e ordens fantasmas — Albion Online.

Cruza cada cotação com a média histórica real (7 dias) e classifica o risco
de ordem fantasma, além de aplicar o teto seguro de +15% para bids.

Exemplo:
    python3 live_market_audit.py --city Lymhurst --items T4_BAG,T5_BAG,T5_RUNE
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from _albion_core import anti_phantom


def _money(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoria de cotações (frescor + fantasma)")
    parser.add_argument("--city", default="Lymhurst", help="Cidade da cotação")
    parser.add_argument("--items", required=True, help="IDs separados por vírgula")
    parser.add_argument("--days", type=int, default=7, help="Janela histórica em dias")
    parser.add_argument("--region", default="americas", choices=["americas", "europe", "asia"])
    parser.add_argument("--json", action="store_true", help="Saída apenas em JSON")
    args = parser.parse_args()

    item_ids = [item.strip() for item in args.items.split(",") if item.strip()]
    audits = [anti_phantom.audit_quote(item, args.city, region=args.region, days=args.days) for item in item_ids]

    result = {"city": args.city, "region": args.region, "audits": audits}

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 80)
    print(f"🔍 AUDITORIA DE COTAÇÕES — {args.city}")
    print("=" * 80)
    print(f"{'Item':<32}{'Cotação':>12}{'Média 7d':>12}{'Desvio':>9}{'Status':>12}")
    print("-" * 80)

    for audit in audits:
        status = audit["phantom_audit"]["status"]
        icon = {"NORMAL": "🟢", "SPIKE_DEMAND": "🟡", "PHANTOM_SUSPECT": "🔴", "DUMP_SUSPECT": "🔴"}.get(status, "⚪")
        print(
            f"{audit['item_name_pt'][:28]:<32}"
            f"{_money(audit['quote_price']):>12}"
            f"{_money(audit['historical_avg_price']):>12}"
            f"{audit['deviation_from_avg_pct']:>8}%"
            f"{icon:>12}"
        )
        if not audit["phantom_audit"]["is_reliable"]:
            print(f"   ⚠️ {audit['phantom_audit']['label']}")
        if not audit["safe_guardrails"]["liquidity_gate_ok"]:
            print(f"   ⚠️ Liquidez baixa: {audit['historical_daily_sales']} vendas/dia (< 1.0).")

    print("\nJSON completo:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
