#!/usr/bin/env python3
"""
Transporte de Facção / Corações · Albion Online.

Calcula o ciclo completo de faction smuggling: recompensa por fardo, rota
(Contrabandista no mapa aberto e retorno à origem), lucro por viagem, prata/hora,
ranking entre venda direta, loop de recompra e manufatura de capas T4.2.

Exemplo:
    python3 calculate_hearts.py --city Lymhurst --silver 1000000 \
        --mount T5_BOAR --risk SAFE_ONLY --pack 7 --premium
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

from _albion_core import hearts


def _money(value) -> str:
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Transporte de Facção / Corações")
    parser.add_argument("--city", required=True, help="Cidade natal (Lymhurst, Thetford, Martlock, Bridgewatch, Fort Sterling)")
    parser.add_argument("--silver", type=int, required=True, help="Saldo de prata disponível")
    parser.add_argument("--mount", default="T5_BOAR", help="Montaria (ex: T5_BOAR, T4_OX, T6_OX)")
    parser.add_argument("--risk", default="SAFE_ONLY", choices=["SAFE_ONLY", "ALLOW_RED_ZONE"])
    parser.add_argument("--mode", default="CONTINUOUS_LOOP", choices=["CONTINUOUS_LOOP", "PATIENT_TRADER"])
    parser.add_argument("--pack", type=int, default=7, choices=[3, 7, 15], help="Fardo: 3 (leve), 7 (médio) ou 15 (pesado)")
    parser.add_argument("--destination", help="Força uma cidade de destino elegível")
    parser.add_argument("--premium", action="store_true", help="Premium ativo (taxa 4%% em vez de 8%%)")
    parser.add_argument("--origin-heart-price", type=int, help="Sobrescreve o preço do coração de origem")
    parser.add_argument("--shadowheart-price", type=int, help="Sobrescreve o preço do Coração Sombrio")
    parser.add_argument("--cape-price", type=int, help="Sobrescreve o preço da Capa T4.2")
    parser.add_argument("--json", action="store_true", help="Saída apenas em JSON")
    args = parser.parse_args()

    plan = hearts.calculate_faction_transport(
        current_city=args.city,
        available_silver=args.silver,
        risk_profile=args.risk,
        has_premium=args.premium,
        mount_type=args.mount,
        session_mode=args.mode,
        pack_size=args.pack,
        target_destination=args.destination,
        origin_heart_price=args.origin_heart_price,
        shadowheart_price=args.shadowheart_price,
        cape_market_price=args.cape_price,
    )

    if args.json or plan.get("status") != "SUCCESS":
        print(json.dumps(plan, indent=2, ensure_ascii=False, default=str))
        return 0 if plan.get("status") == "SUCCESS" else 1

    best = plan["best_route_recommended"]
    financials = best["financials"]

    print("=" * 78)
    print("❤️ TRANSPORTE DE FACÇÃO · ALBION ONLINE")
    print("=" * 78)
    print(
        f"Origem: {plan['origin_city']} | Fardo: {plan['pack_spec']['hearts_in']} corações "
        f"({plan['pack_spec']['weight_kg']} kg) | Montaria: {args.mount}"
    )
    print(
        f"Risco: {args.risk} | Modo: {args.mode} | Premium: {'sim (4%)' if args.premium else 'não (8%)'} | "
        f"Saldo: {_money(args.silver)} 🪙"
    )
    print(f"Destino: {best['destination_city']} ({best['route_category']}, {best['risk_zone']})")
    print(f"ONDE VENDER: {plan['where_to_sell']}")

    print("\n" + "=" * 78)
    print("🏆 RANKING DE ESTRATÉGIAS")
    print("=" * 78)
    for row in plan["ranked_strategies"]:
        print(
            f"#{row['rank']} {row['title']}\n"
            f"   Lucro/viagem: {_money(row['net_profit_per_trip'])} 🪙 | "
            f"Prata/hora: {_money(row['silver_per_hour'])} 🪙 | Esforço: {row['effort_level']}"
        )

    print("\n" + "=" * 78)
    print("💰 FINANCEIRO DA ROTA PRINCIPAL")
    print("=" * 78)
    print(f"Custo do fardo:     {_money(financials['cost_in_silver'])} 🪙")
    print(f"Retorno líquido:    {_money(financials['net_return_silver'])} 🪙")
    print(f"Lucro líquido:      {_money(financials['net_profit_silver'])} 🪙 (ROI {financials['roi_pct']}%)")
    print(f"Prata/hora:         {_money(financials['silver_per_hour'])} 🪙")
    print(f"Corações:           {best['hearts_in']} → {best['hearts_out']} (+{best['hearts_delta']})")

    protocol = plan["operational_protocol"]
    print("\n" + "=" * 78)
    print("🧭 PROTOCOLO OPERACIONAL")
    print("=" * 78)
    for rule in protocol.get("critical_rules", []):
        print(f"- {rule}")

    if plan.get("price_statement_markdown"):
        print("\n" + plan["price_statement_markdown"])

    if plan.get("cape_investment_markdown"):
        print("\n" + plan["cape_investment_markdown"])

    print("\n" + "=" * 78)
    print("🎯 VEREDITO DEFINITIVO")
    print("=" * 78)
    print(plan["definitive_verdict"])

    print("\nJSON completo:")
    print(json.dumps(plan, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
