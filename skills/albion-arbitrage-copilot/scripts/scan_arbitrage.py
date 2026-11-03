#!/usr/bin/env python3
"""
Scanner de Arbitragem Intercidades · Albion Online.

Compara o menor sell order das capitais de origem com o melhor destino de venda
(capital real ou Black Market), já descontando impostos e setup fee.

Exemplo:
    python3 scan_arbitrage.py --origin Thetford --destination Martlock --premium --min-roi 15
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

from _albion_core import economics
from _albion_core.http import ROYAL_CITIES

DEFAULT_ITEMS = [
    "T4_BAG", "T5_BAG", "T6_BAG",
    "T4_CAPE", "T5_CAPE", "T6_CAPE",
    "T4_ARMOR_PLATE_SET1", "T5_ARMOR_PLATE_SET1",
    "T4_MAIN_SWORD", "T5_MAIN_SWORD",
    "T4_MAIN_AXE", "T5_MAIN_AXE",
    "T4_METALBAR", "T5_METALBAR",
    "T4_LEATHER", "T5_LEATHER",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Scanner de Arbitragem Intercidades")
    parser.add_argument("--origin", help="Cidade de compra (ex: Thetford)")
    parser.add_argument("--destination", help="Cidade de venda (ex: Martlock)")
    parser.add_argument("--items", help="IDs separados por vírgula (ex: T4_BAG,T5_BAG)")
    parser.add_argument("--min-roi", type=float, default=12.0, help="ROI mínimo em %% (padrão: 12)")
    parser.add_argument("--safe-only", action="store_true", help="Apenas capitais reais (sem Caerleon/Black Market)")
    parser.add_argument("--premium", action="store_true", help="Premium ativo (taxa 4%% em vez de 8%%)")
    parser.add_argument(
        "--region", default="americas", choices=["americas", "europe", "asia"], help="Servidor"
    )
    parser.add_argument("--json", action="store_true", help="Saída apenas em JSON")
    args = parser.parse_args()

    sources = [args.origin] if args.origin else ROYAL_CITIES

    if args.safe_only:
        targets = ROYAL_CITIES
    elif args.destination:
        targets = [args.destination]
    else:
        targets = ROYAL_CITIES + ["Caerleon", "Black Market"]

    items = [item.strip() for item in args.items.split(",")] if args.items else DEFAULT_ITEMS

    result = economics.find_arbitrage(
        item_ids=items,
        source_cities=sources,
        target_cities=targets,
        min_roi_pct=args.min_roi,
        has_premium=args.premium,
        region=args.region,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 68)
    print("🚚 ARBITRAGEM INTERCIDADES · ALBION ONLINE")
    print(f"Origem(ns): {', '.join(sources)}")
    print(f"Destino(s): {', '.join(targets)}")
    print(f"Itens: {len(items)} | ROI mínimo: {args.min_roi}% | Premium: {'sim' if args.premium else 'não'}")
    print("=" * 68)

    opportunities = result.get("opportunities", [])
    if not opportunities:
        print("Nenhuma oportunidade passou o filtro de ROI. Tente --min-roi menor ou mais itens.")
        return 0

    print(f"\n{'Item':<34}{'Compra':>16}{'Venda':>16}{'Lucro/un':>12}{'ROI':>8}")
    print("-" * 86)
    for row in opportunities:
        label = f"{row['item_name_pt'][:30]} Q{row['quality']}"
        buy = f"{row['buy_city']} {row['buy_price']:,}".replace(",", ".")
        sell = f"{row['sell_city']} {row['sell_price']:,}".replace(",", ".")
        profit = f"{row['unit_profit']:,}".replace(",", ".")
        flag = " 🛡️" if row["is_safe_route"] else " ⚠️"
        print(f"{label:<34}{buy:>16}{sell:>16}{profit:>12}{row['roi_pct']:>7}%{flag}")

    print("\nJSON completo:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
