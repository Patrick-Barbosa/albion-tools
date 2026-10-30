"""
Ferramentas MCP para Inteligência de Transporte de Facção e Economia de Corações.
"""

from typing import Dict, Any, Optional, List
from ..core.faction_transport import (
    calculate_faction_transport_plan,
    simulate_post_trip_decision_tree,
    HEARTS_METADATA,
    FACTION_CAPE_METADATA,
    FACTION_PACK_SPECS,
    TRANSMUTE_FEE_SILVER
)
from ..core.cape_crafting import (
    evaluate_cape_vs_raw_heart_profit,
    calculate_cape_crafting_cost,
    optimize_cape_crafting_for_heart,
    resolve_cape_metadata
)
import logging

logger = logging.getLogger("albion_mcp.faction_tools")

try:
    from ..core.aodp_client import aodp_client
except ImportError:
    aodp_client = None

try:
    from ..core.nats_client import nats_subscriber
except ImportError:
    nats_subscriber = None



async def albion_calculate_faction_transport(
    current_city: str,
    available_silver: int,
    risk_profile: str,
    has_premium: bool,
    mount_type: str,
    session_mode: str,
    pack_size: int,
    target_destination: Optional[str] = None,
    origin_heart_price: Optional[int] = None,
    shadowheart_price: Optional[int] = None,
    cape_market_price: Optional[int] = None
) -> Dict[str, Any]:
    """
    Calcula e planeja missões de transporte de corações de facção (Faction Smuggling).

    Implementa o contrato Round-Trip oficial (ida ao contrabandista no mapa aberto e retorno
    OBRIGATÓRIO à cidade de origem), pesagem física dos fardos (125 kg, 668 kg, 1623 kg),
    dimensionamento de montarias anti-gank e árvore de decisão completa e ranqueada.

    ATENÇÃO OPERACIONAL:
    - O jogador NUNCA entra em Caerleon nem em outra capital estrangeira durante o transporte.
    - 100% das vendas, transmutações e confecção de capas acontecem no Mercado da cidade de ORIGEM.
    - A Capa recomendada é sempre a Capa da cidade de ORIGEM (ex: Capa de Lymhurst em Lymhurst).

    GUARDRAILS OBRIGATÓRIOS:
    - current_city: Cidade natal ('Lymhurst', 'Bridgewatch', 'Fort Sterling', 'Thetford', 'Martlock').
    - available_silver: Saldo de prata na carteira para orçar fardo ou transmutação.
    - risk_profile: 'SAFE_ONLY' (apenas Zonas Azuis/Amarelas) ou 'ALLOW_RED_ZONE' (permite Caerleon / Full Loot).
    - has_premium: True (4% imposto) ou False (8% imposto).
    - mount_type: Montaria utilizada (padrão: 'T5_BOAR' ou bois 'T4_OX'..'T8_OX').
    - session_mode: 'CONTINUOUS_LOOP' (giro rápido sem parar) ou 'PATIENT_TRADER' (ordens de venda / capas).
    - pack_size: Quantidade de corações do fardo (3 = Leve/125kg, 7 = Médio/668kg, 15 = Pesado/1623kg).
    - target_destination: Cidade de destino opcional caso o jogador queira forçar uma rota específica.
    - origin_heart_price: Sobrescrita manual da cotação do coração de origem (opcional).
    - shadowheart_price: Sobrescrita manual da cotação do coração sombrio (opcional).
    - cape_market_price: Sobrescrita manual da cotação da Capa T4.2 no mercado local (opcional).
    """
    norm_city = current_city.strip().title()
    all_heart_ids = [h["item_id"] for h in HEARTS_METADATA.values()]
    legacy_heart_ids = [h.get("legacy_id") for h in HEARTS_METADATA.values() if h.get("legacy_id")]
    
    # Lista de Capas T4.2 para consulta em lote na API
    all_cape_ids = []
    for c_meta in FACTION_CAPE_METADATA.values():
        all_cape_ids.append(f"T4_{c_meta['item_id_base']}@2")
        alt = c_meta.get("alternative_cape")
        if alt:
            all_cape_ids.append(f"T4_{alt['item_id']}@2")

    # Insumos de Manufatura e Encantamento de Capas
    cape_materials = [
        "T4_CAPE",
        "T4_RUNE",
        "T4_SOUL",
        "T4_CAPEITEM_SMUGGLER_BP",
        "T4_CREST_FW_LYMHURST",
        "T4_CREST_FW_FORTSTERLING",
        "T4_CREST_FW_BRIDGEWATCH",
        "T4_CREST_FW_THETFORD",
        "T4_CREST_FW_MARTLOCK",
        "T4_CREST_FW_CAERLEON",
        "T4_CREST_HERETIC",
        "T4_CREST_UNDEAD",
        "T4_CREST_DEMON",
        "T4_CREST_MORGANA",
        "T4_CREST_KEEPER",
    ]

    items_to_query = all_heart_ids + legacy_heart_ids + all_cape_ids + cape_materials
    live_prices = {}
    item_metadata_quotes = {}

    # =========================================================================
    # HIERARQUIA DETERMINÍSTICA DE COTAÇÕES: API > NATS > MANUAL
    # =========================================================================

    # -------------------------------------------------------------------------
    # 1. PRIORIDADE 1: API (AODP REST)
    # -------------------------------------------------------------------------
    if aodp_client is not None:
        try:
            raw_prices = await aodp_client.get_current_prices(
                item_ids=items_to_query,
                locations=[norm_city, "Caerleon"]
            )
            quotes_by_item_city = {}
            for p in raw_prices:
                it_id = p.get("item_id")
                p_city = (p.get("city") or "").title()
                key = (it_id, p_city)
                if key not in quotes_by_item_city:
                    quotes_by_item_city[key] = []
                quotes_by_item_city[key].append(p)

            caerleon_tokens = {"T1_FACTION_CAERLEON_TOKEN_1", "T4_HEART_UNDEAD"}

            for (it_id, p_city), plist in quotes_by_item_city.items():
                if p_city == norm_city or (it_id in caerleon_tokens and p_city in ("Caerleon", norm_city)):
                    # Procura ordens de venda ativas (> 0) em qualquer qualidade
                    active_sells = [x for x in plist if x.get("sell_price_min", 0) > 0]
                    if active_sells:
                        best = min(active_sells, key=lambda x: x.get("sell_price_min"))
                        price_val = best["sell_price_min"]
                        order_type = "Sell Order Min"
                        order_date = best.get("sell_price_min_date") or "Tempo Real"
                    else:
                        active_buys = [x for x in plist if x.get("buy_price_max", 0) > 0]
                        if active_buys:
                            best = max(active_buys, key=lambda x: x.get("buy_price_max"))
                            price_val = best["buy_price_max"]
                            order_type = "Buy Order Max"
                            order_date = best.get("buy_price_max_date") or "Tempo Real"
                        else:
                            continue

                    if it_id not in live_prices:
                        live_prices[it_id] = price_val
                        item_metadata_quotes[it_id] = {
                            "price": price_val,
                            "source": "API_AODP_LIVE",
                            "source_label": "🔴 API AODP",
                            "city": p_city,
                            "order_type": order_type,
                            "date": order_date
                        }

                    # Sincroniza tokens oficiais e IDs legados
                    for h_meta in HEARTS_METADATA.values():
                        if it_id in (h_meta["item_id"], h_meta.get("legacy_id")):
                            off_id = h_meta["item_id"]
                            leg_id = h_meta.get("legacy_id")
                            live_prices[off_id] = price_val
                            item_metadata_quotes[off_id] = item_metadata_quotes[it_id]
                            if leg_id:
                                live_prices[leg_id] = price_val
                                item_metadata_quotes[leg_id] = item_metadata_quotes[it_id]
        except Exception as e:
            logger.debug(f"AODP batch fetch: {e}")

    # -------------------------------------------------------------------------
    # 2. PRIORIDADE 2: NATS (Streaming Firehose Buffer em Tempo Real)
    # -------------------------------------------------------------------------
    missing_after_api = [it for it in items_to_query if it not in live_prices]
    if missing_after_api and nats_subscriber is not None:
        try:
            nats_orders = nats_subscriber.get_live_orders(
                item_ids=missing_after_api,
                cities=[norm_city, "Caerleon"],
                max_age_seconds=3600.0
            )
            for ord_data in nats_orders:
                it_id = ord_data.get("item_id")
                p_city = (ord_data.get("city") or "").title()
                p_val = ord_data.get("price", 0)
                if p_val > 0 and it_id not in live_prices:
                    live_prices[it_id] = p_val
                    age_s = ord_data.get("age_seconds", 0)
                    item_metadata_quotes[it_id] = {
                        "price": p_val,
                        "source": "NATS_STREAM_LIVE",
                        "source_label": "⚡ NATS LIVE",
                        "city": p_city,
                        "order_type": "Live Stream Order",
                        "date": f"{age_s}s atrás" if age_s else "Tempo Real"
                    }
                    for h_meta in HEARTS_METADATA.values():
                        if it_id in (h_meta["item_id"], h_meta.get("legacy_id")):
                            off_id = h_meta["item_id"]
                            leg_id = h_meta.get("legacy_id")
                            live_prices[off_id] = p_val
                            item_metadata_quotes[off_id] = item_metadata_quotes[it_id]
                            if leg_id:
                                live_prices[leg_id] = p_val
                                item_metadata_quotes[leg_id] = item_metadata_quotes[it_id]
        except Exception as e:
            logger.debug(f"NATS fallback error: {e}")

    # -------------------------------------------------------------------------
    # 3. PRIORIDADE 3: MANUAL (Input do Jogador / Fallback Calibrado)
    # -------------------------------------------------------------------------
    origin_heart_meta = HEARTS_METADATA.get(norm_city, {})
    origin_heart_id = origin_heart_meta.get("item_id", "T1_FACTION_FOREST_TOKEN_1")
    origin_heart_legacy = origin_heart_meta.get("legacy_id", "T4_HEART_WOOD")
    shadowheart_id = HEARTS_METADATA.get("Caerleon", {}).get("item_id", "T1_FACTION_CAERLEON_TOKEN_1")
    shadowheart_legacy = HEARTS_METADATA.get("Caerleon", {}).get("legacy_id", "T4_HEART_UNDEAD")
    origin_cape_id = f"T4_{FACTION_CAPE_METADATA.get(norm_city, {}).get('item_id_base', '')}@2"

    # 3.1 Sobrescritas explícitas do jogador
    if origin_heart_price and origin_heart_price > 0:
        live_prices[origin_heart_id] = origin_heart_price
        live_prices[origin_heart_legacy] = origin_heart_price
        manual_quote = {
            "price": origin_heart_price,
            "source": "MANUAL_INPUT",
            "source_label": "✍️ MANUAL",
            "city": norm_city,
            "order_type": "Informado pelo Jogador",
            "date": "Manual"
        }
        item_metadata_quotes[origin_heart_id] = manual_quote
        item_metadata_quotes[origin_heart_legacy] = manual_quote

    if shadowheart_price and shadowheart_price > 0:
        live_prices[shadowheart_id] = shadowheart_price
        live_prices[shadowheart_legacy] = shadowheart_price
        manual_quote = {
            "price": shadowheart_price,
            "source": "MANUAL_INPUT",
            "source_label": "✍️ MANUAL",
            "city": norm_city,
            "order_type": "Informado pelo Jogador",
            "date": "Manual"
        }
        item_metadata_quotes[shadowheart_id] = manual_quote
        item_metadata_quotes[shadowheart_legacy] = manual_quote

    if cape_market_price and cape_market_price > 0:
        live_prices[origin_cape_id] = cape_market_price
        item_metadata_quotes[origin_cape_id] = {
            "price": cape_market_price,
            "source": "MANUAL_INPUT",
            "source_label": "✍️ MANUAL",
            "city": norm_city,
            "order_type": "Informado pelo Jogador",
            "date": "Manual"
        }

    # 3.2 Calibração de fallback para itens sem ordens ativas na API nem no NATS
    default_prices = {
        # Tokens Oficiais
        "T1_FACTION_FOREST_TOKEN_1": 45000,
        "T1_FACTION_MOUNTAIN_TOKEN_1": 46000,
        "T1_FACTION_STEPPE_TOKEN_1": 44000,
        "T1_FACTION_SWAMP_TOKEN_1": 47000,
        "T1_FACTION_HIGHLAND_TOKEN_1": 43000,
        "T1_FACTION_CAERLEON_TOKEN_1": 62000,
        # IDs Legados
        "T4_HEART_WOOD": 45000,
        "T4_HEART_MOUNTAIN": 46000,
        "T4_HEART_BEAST": 44000,
        "T4_HEART_SWAMP": 47000,
        "T4_HEART_ROCK": 43000,
        "T4_HEART_UNDEAD": 62000,
        # Capas Reais T4.2
        "T4_CAPEITEM_FW_LYMHURST@2": 175000,
        "T4_CAPEITEM_FW_FORTSTERLING@2": 160000,
        "T4_CAPEITEM_FW_BRIDGEWATCH@2": 165000,
        "T4_CAPEITEM_FW_THETFORD@2": 170000,
        "T4_CAPEITEM_FW_MARTLOCK@2": 160000,
        "T4_CAPEITEM_FW_CAERLEON@2": 175000,
        # Capas Mob / Especiais T4.2
        "T4_CAPEITEM_SMUGGLER@2": 240000,
        "T4_CAPEITEM_HERETIC@2": 185000,
        "T4_CAPEITEM_UNDEAD@2": 260000,
        "T4_CAPEITEM_MORGANA@2": 180000,
        "T4_CAPEITEM_DEMON@2": 195000,
        "T4_CAPEITEM_KEEPER@2": 175000,
        # Insumos de Manufatura e Encantamento de Capas
        "T4_CAPE": 3642,
        "T4_CAPEITEM_SMUGGLER_BP": 11976,
        "T4_RUNE": 8,
        "T4_SOUL": 82,
        "T4_CREST_FW_LYMHURST": 15000,
        "T4_CREST_FW_FORTSTERLING": 15000,
        "T4_CREST_FW_BRIDGEWATCH": 15000,
        "T4_CREST_FW_THETFORD": 15000,
        "T4_CREST_FW_MARTLOCK": 15000,
        "T4_CREST_FW_CAERLEON": 16000,
        "T4_CREST_HERETIC": 18000,
        "T4_CREST_UNDEAD": 22000,
        "T4_CREST_DEMON": 18000,
        "T4_CREST_MORGANA": 17000,
        "T4_CREST_KEEPER": 16000,
    }
    for k, v in default_prices.items():
        if k not in live_prices:
            live_prices[k] = v
            item_metadata_quotes[k] = {
                "price": v,
                "source": "MANUAL_FALLBACK",
                "source_label": "✍️ MANUAL",
                "city": norm_city,
                "order_type": "Referência (Sem API/NATS)",
                "date": "Sem ordens na API/NATS"
            }

    # Determina a fonte preponderante utilizada
    sources_used = {q["source"] for q in item_metadata_quotes.values()}
    if "API_AODP_LIVE" in sources_used:
        price_source = "API_AODP_LIVE"
    elif "NATS_STREAM_LIVE" in sources_used:
        price_source = "NATS_STREAM_LIVE"
    else:
        price_source = "MANUAL"

    # 4. Executa o plano com os preços identificados
    plan = calculate_faction_transport_plan(
        current_city=current_city,
        available_silver=available_silver,
        risk_profile=risk_profile,
        has_premium=has_premium,
        mount_type=mount_type,
        session_mode=session_mode,
        pack_size=pack_size,
        target_destination=target_destination,
        mock_heart_prices=live_prices,
        material_prices=live_prices
    )

    # 5. Montagem do Extrato de Cotações Utilizadas (Transparência Total)
    def _fmt(val: float) -> str:
        return f"{int(val):,}".replace(",", ".")

    extrato_de_precos = []
    items_to_audit = [
        (origin_heart_id, origin_heart_meta.get("name_pt", "Coração da Origem")),
        (shadowheart_id, "Coração Sombrio"),
        (origin_cape_id, f"Capa de {norm_city} T4.2"),
    ]
    natal_alt = FACTION_CAPE_METADATA.get(norm_city, {}).get("alternative_cape")
    if natal_alt:
        alt_it_id = f"T4_{natal_alt['item_id']}@2"
        items_to_audit.append((alt_it_id, f"{natal_alt['name_pt']} T4.2"))
    items_to_audit.append(("T4_CAPEITEM_SMUGGLER@2", "Capa de Contrabandista T4.2"))
    # Insumos essenciais de manufatura
    items_to_audit.append(("T4_CAPE", "Capa Comum T4 (Base)"))
    items_to_audit.append(("T4_CAPEITEM_SMUGGLER_BP", "Ornamento de Contrabandista"))
    items_to_audit.append(("T4_RUNE", "Runa T4 (Encantamento .1)"))
    items_to_audit.append(("T4_SOUL", "Alma T4 (Encantamento .2)"))

    md_lines = [
        "| Item | Mercado | Cotação Utilizada | Fonte da Cotação | Tipo de Preço | Status / Idade |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |"
    ]

    for it_id, it_name in items_to_audit:
        q_info = item_metadata_quotes.get(it_id, {
            "price": live_prices.get(it_id, 0),
            "source": "MANUAL",
            "source_label": "✍️ MANUAL",
            "city": norm_city,
            "order_type": "Referência de Mercado",
            "date": "Auditado"
        })
        src_tag = q_info.get("source_label", "✍️ MANUAL")
        p_val = q_info["price"]
        extrato_de_precos.append({
            "item_id": it_id,
            "item_name": it_name,
            "city": q_info["city"],
            "unit_price_silver": p_val,
            "source": q_info["source"],
            "source_label": src_tag,
            "order_type": q_info["order_type"],
            "date_or_status": q_info["date"]
        })
        md_lines.append(
            f"| **{it_name}** | {q_info['city']} | {_fmt(p_val)} 🪙 | {src_tag} | {q_info['order_type']} | {q_info['date']} |"
        )

    price_statement_markdown = "\n".join(md_lines)

    # Anexa transparência total de preços, insumos e origens
    plan["extrato_de_precos"] = extrato_de_precos
    plan["price_statement_markdown"] = price_statement_markdown
    plan["cape_investment_audit"] = plan.get("cape_investment_audit") or (plan.get("recommended_cape") or {}).get("cape_investment_audit", {})
    plan["cape_investment_markdown"] = plan.get("cape_investment_markdown") or (plan.get("recommended_cape") or {}).get("cape_investment_markdown", "")
    plan["price_audit"] = {
        "price_source": price_source,
        "evaluated_city": norm_city,
        "hierarchy_applied": "API > NATS > MANUAL",
        "origin_heart_quote_used": live_prices.get(origin_heart_id),
        "shadowheart_quote_used": live_prices.get("T4_HEART_UNDEAD"),
        "cape_reference_quote_used": live_prices.get(origin_cape_id),
        "extrato_de_precos": extrato_de_precos,
        "disclaimer": f"Todas as compras, vendas e cotações foram calibradas exclusivamente para o mercado de {norm_city} seguindo a hierarquia API > NATS > MANUAL."
    }

    return plan



def albion_simulate_heart_cycle(
    origin_city: str,
    destination_city: str,
    pack_size: int,
    num_cycles: int,
    has_premium: bool,
    origin_heart_price: Optional[int] = None,
    shadowheart_price: Optional[int] = None
) -> Dict[str, Any]:
    """
    Simula a execução contínua de múltiplos ciclos de transporte (ex: 1 hora = 6 viagens de Javali T5).

    Compara os 3 caminhos de reciclagem de capital:
    1. Injeção Externa de Prata (recompra contínua de mercado e estocagem de sombrios).
    2. Expansão Perpétua por Transmutação Total (11 sombrios -> 11 arbóreos a 5.780 prata).
    3. Loop Híbrido Autossustentável (transmuta 7 para rodar de novo e vende os 4 restantes via Instant Sell).

    TODOS os parâmetros operacionais são obrigatórios, refletindo a realidade do jogador.
    """
    tax_rate = 0.04 if has_premium else 0.08
    is_caerleon = (destination_city.lower() == "caerleon")
    effective_origin_price = origin_heart_price or 45000
    effective_shadowheart_price = shadowheart_price or 62000

    # Recompensa por viagem (ex: 7 -> 11 em Caerleon)
    from ..core.faction_transport import calculate_faction_route_reward
    hearts_out = calculate_faction_route_reward(origin_city, destination_city, pack_size)
    hearts_delta = hearts_out - pack_size

    # Tempo total estimado (10 min por ciclo de Javali T5)
    total_minutes = num_cycles * 10.0

    # 1. Caminho 1: Injeção de Prata Externa
    capital_needed_c1 = num_cycles * pack_size * effective_origin_price
    total_shadowhearts_accum_c1 = num_cycles * hearts_out
    gross_revenue_c1 = total_shadowhearts_accum_c1 * effective_shadowheart_price
    net_revenue_c1 = int(gross_revenue_c1 * (1.0 - tax_rate))
    net_profit_c1 = net_revenue_c1 - capital_needed_c1

    # 2. Caminho 2: Expansão Perpétua Total (Transmuta todos hearts_out a 5.780)
    initial_seed_cost_c2 = pack_size * effective_origin_price
    transmute_cost_per_cycle_c2 = hearts_out * TRANSMUTE_FEE_SILVER if is_caerleon else 0
    total_transmute_cost_c2 = num_cycles * transmute_cost_per_cycle_c2
    surplus_origin_hearts_stored_c2 = num_cycles * hearts_delta if is_caerleon else 0
    surplus_valuation_c2 = surplus_origin_hearts_stored_c2 * effective_origin_price

    # 3. Caminho 3: Loop Híbrido Autossustentável (Transmuta pack_size e vende hearts_delta imediatamente)
    initial_seed_cost_c3 = pack_size * effective_origin_price
    transmute_required_per_cycle_c3 = pack_size * TRANSMUTE_FEE_SILVER if is_caerleon else 0
    total_transmute_cost_c3 = num_cycles * transmute_required_per_cycle_c3
    total_surplus_sold_c3 = num_cycles * hearts_delta
    gross_surplus_revenue_c3 = total_surplus_sold_c3 * effective_shadowheart_price
    net_surplus_revenue_c3 = int(gross_surplus_revenue_c3 * (1.0 - tax_rate))
    liquid_cash_in_pocket_c3 = net_surplus_revenue_c3 - total_transmute_cost_c3

    def _fmt(val: float) -> str:
        return f"{int(val):,}".replace(",", ".")

    definitive_verdict = (
        f"👉 VEREDITO DEFINITIVO: O Loop Híbrido Autossustentável (Caminho 3) é o campeão para sessões contínuas! "
        f"Transmuta {pack_size} corações a cada viagem para rodar sem tirar dinheiro do banco e embolsa "
        f"{_fmt(liquid_cash_in_pocket_c3)} 🪙 de prata líquida pura no bolso em {num_cycles} viagens ({_fmt((liquid_cash_in_pocket_c3 / total_minutes) * 60)} 🪙/hora). "
        f"Toda a transmutação e venda dos excedentes ocorre no Mercado Municipal de {origin_city}."
    )

    return {
        "simulation_parameters": {
            "origin_city": origin_city,
            "destination_city": destination_city,
            "pack_size": pack_size,
            "hearts_returned_per_trip": hearts_out,
            "hearts_profit_per_trip": hearts_delta,
            "num_cycles": num_cycles,
            "total_playtime_minutes": total_minutes,
            "has_premium": has_premium
        },
        "where_to_sell": f"Mercado Municipal de {origin_city}",
        "operational_protocol": {
            "origin_city": origin_city,
            "rule": f"Você NUNCA entra em Caerleon nem em outra capital faccionado. As entregas são nos contrabandistas no mapa aberto e todo resgate e comercialização é 100% no Mercado de {origin_city}."
        },
        "definitive_verdict": definitive_verdict,
        "path_1_external_reinvestment": {
            "strategy": "Comprar fardo no mercado a cada ciclo e guardar todos os corações recebidos",
            "capital_required_silver": capital_needed_c1,
            "total_hearts_accumulated": total_shadowhearts_accum_c1,
            "net_revenue_if_sold_silver": net_revenue_c1,
            "net_profit_silver": net_profit_c1,
            "silver_per_hour": int((net_profit_c1 / total_minutes) * 60)
        },
        "path_2_perpetual_expansion": {
            "strategy": f"Transmutar todos os corações recebidos em corações da sua cidade para expandir o estoque",
            "initial_seed_capital": initial_seed_cost_c2,
            "total_transmute_fees_paid": total_transmute_cost_c2,
            "surplus_origin_hearts_in_chest": surplus_origin_hearts_stored_c2,
            "surplus_equity_valuation_silver": surplus_valuation_c2,
            "net_equity_gain_silver": surplus_valuation_c2 - total_transmute_cost_c2
        },
        "path_3_hybrid_autoloop": {
            "strategy": "Transmutar apenas o necessário para a próxima viagem e vender o lucro líquido imediatamente",
            "initial_seed_capital": initial_seed_cost_c3,
            "total_transmute_fees_paid": total_transmute_cost_c3,
            "surplus_hearts_sold_for_cash": total_surplus_sold_c3,
            "liquid_cash_profit_in_pocket": liquid_cash_in_pocket_c3,
            "silver_per_hour": int((liquid_cash_in_pocket_c3 / total_minutes) * 60)
        }
    }


def albion_evaluate_heart_downstream(
    city_faction: str,
    tier: int,
    enchantment: int,
    target_quality: int,
    heart_market_price: int,
    cape_market_sell_price: int,
    has_premium: bool
) -> Dict[str, Any]:
    """
    Avalia a esteira downstream de manufatura de Capas de Facção (T4..T8).

    Compara se é mais lucrativo vender os corações brutos ou utilizá-los para
    confeccionar Capas de Facção encantadas (.1/.2/.3) com reroll de qualidade.
    Compara automaticamente todas as capas elegíveis para o coração (Real vs Mob vs Especial).

    TODOS os parâmetros operacionais são obrigatórios.
    """
    cape_meta = resolve_cape_metadata(city_faction)
    res = evaluate_cape_vs_raw_heart_profit(
        city_faction=city_faction,
        tier=tier,
        enchantment=enchantment,
        target_quality=target_quality,
        heart_market_price=heart_market_price,
        cape_market_sell_price=cape_market_sell_price,
        has_premium=has_premium
    )
    res["where_to_sell"] = f"Mercado Municipal de {cape_meta['city']}"
    res["target_cape_name"] = f"{res['cape_name_pt']} T{tier}.{enchantment}"
    res["operational_instructions"] = (
        f"A confecção de {res['cape_name_pt']} exige o coração {cape_meta['heart_name_pt']}. "
        f"Caso seus corações sejam Sombrios (obtidos em rota de Caerleon) e a capa seja de outra cidade/facção, "
        f"transmute-os no transmutador municipal de {cape_meta['city']} (taxa fixa oficial de 5.780 🪙) "
        f"antes de confeccionar a capa."
    )

    # Otimização downstream: compara com todas as outras capas que usam o mesmo coração
    try:
        opt = optimize_cape_crafting_for_heart(
            heart_or_city=cape_meta["heart_id"],
            tier=tier,
            enchantment=enchantment,
            target_quality=target_quality,
            heart_market_price=heart_market_price,
            custom_cape_prices={res["cape_id"]: cape_market_sell_price},
            has_premium=has_premium
        )
        res["all_eligible_capes_ranked"] = opt["ranked_capes"]
        res["best_cape_recommendation"] = opt["verdict"]
        res["best_cape_name"] = opt["best_cape_name"]
        res["delta_silver_advantage"] = opt["delta_silver_advantage"]
    except Exception:
        pass

    return res

