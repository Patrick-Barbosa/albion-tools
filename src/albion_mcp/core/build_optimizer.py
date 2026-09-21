"""
Motor de Otimização de Builds Econômicas por Tier Equivalente para Albion Online.

Calcula e compara combinações de equipamentos (ex: 4.3, 5.2, 6.1 e 7.0 para Tier 7 Equivalente)
para identificar o menor custo possível na montagem de uma build completa em uma cidade específica.
"""

import os
import re
import sqlite3
import logging
from typing import List, Dict, Any, Optional, Tuple

from .metadata import metadata_manager, ITEMS_FILE, DATA_DIR, QUALITY_NAMES
from .aodp_client import aodp_client
from .databricks_client import databricks_client
from .nats_client import CITY_TO_LOCATION_ID

logger = logging.getLogger("albion_mcp.build_optimizer")

TIER_AFFIXES_PT = [
    " do adepto", " do perito", " do mestre", " do grão-mestre", " do grao-mestre",
    " do ancião", " do anciao", " do iniciante", " do novato", " do calouro"
]

TIER_AFFIXES_EN = [
    "adept's ", "expert's ", "master's ", "grandmaster's ", "elder's ",
    "journeyman's ", "novice's ", "beginner's "
]


def clean_item_query(name: str) -> str:
    """Remove afixos de tier tanto em português quanto em inglês."""
    cleaned = name.strip()
    c_lower = cleaned.lower()

    for aff in TIER_AFFIXES_PT:
        if c_lower.endswith(aff):
            return cleaned[:len(cleaned) - len(aff)].strip()

    for aff in TIER_AFFIXES_EN:
        if c_lower.startswith(aff):
            return cleaned[len(aff):].strip()

    return cleaned


def resolve_item_family(query: str) -> Optional[Dict[str, Any]]:
    """
    Resolve uma busca textual ou ID técnico para uma família base de itens.
    Exemplos:
    - 'Machado de Guerra' -> 'MAIN_AXE'
    - 'T4_MAIN_AXE' -> 'MAIN_AXE'
    - 'Capuz de Assassino' -> 'HEAD_LEATHER_SET3'
    - 'Mercenary Jacket' -> 'ARMOR_LEATHER_SET1'
    """
    metadata_manager.ensure_data_loaded()
    q = query.strip()
    if not q:
        return None

    # Caso 1: ID técnico direto (ex: T4_MAIN_AXE, T4_MAIN_AXE@1, MAIN_AXE)
    m = re.match(r"^(?:T\d_)?([A-Z0-9_]+)(?:@\d)?$", q, re.IGNORECASE)
    if m:
        base_cand = m.group(1).upper()
        # Valida se existe ao menos um item com esse base_id no catálogo
        for t in [4, 5, 6, 7, 8, 3]:
            cand_id = f"T{t}_{base_cand}"
            if cand_id in metadata_manager.item_names:
                pt_name = clean_item_query(metadata_manager.get_item_name(cand_id))
                en_name = clean_item_query(metadata_manager.get_item_name_en(cand_id))
                return {
                    "base_identifier": base_cand,
                    "name_pt": pt_name,
                    "name_en": en_name,
                    "category": metadata_manager.get_category_for_item(cand_id),
                    "slot_type": metadata_manager.get_slot_type(cand_id)
                }

    # Caso 2: Busca por texto (PT-BR ou EN)
    cleaned_query = clean_item_query(q).lower()

    # Busca no catálogo de metadados
    catalog = metadata_manager.get_raw_catalog()

    exact_matches = []
    prefix_matches = []
    substring_matches = []

    for item in catalog:
        uname = item.get("UniqueName", "")
        if "@" in uname:
            continue

        pt = (item.get("LocalizedNames") or {}).get("PT-BR", "").strip()
        en = (item.get("LocalizedNames") or {}).get("EN-US", "").strip()
        if not pt and not en:
            continue

        clean_pt = clean_item_query(pt).lower()
        clean_en = clean_item_query(en).lower()
        base_id = re.sub(r"^T\d_", "", uname)

        # Prioriza T4 a T8 para equipamentos
        tier_str = metadata_manager.get_tier(uname)
        tier_num = int(tier_str.replace("T", "")) if tier_str.replace("T", "").isdigit() else 0

        info = {
            "base_identifier": base_id,
            "name_pt": clean_item_query(pt),
            "name_en": clean_item_query(en),
            "category": metadata_manager.get_category_for_item(uname),
            "slot_type": metadata_manager.get_slot_type(uname),
            "tier_num": tier_num,
            "sample_id": uname
        }

        if cleaned_query == clean_pt or cleaned_query == clean_en:
            exact_matches.append(info)
        elif clean_pt.startswith(cleaned_query) or clean_en.startswith(cleaned_query):
            prefix_matches.append(info)
        elif cleaned_query in clean_pt or cleaned_query in clean_en or cleaned_query in uname.lower():
            substring_matches.append(info)

    chosen_list = exact_matches or prefix_matches or substring_matches
    if not chosen_list:
        return None

    # Ordena para preferir itens de tier 4 ou superior
    chosen_list.sort(key=lambda x: (x["tier_num"] >= 4, x["tier_num"]), reverse=True)
    best = chosen_list[0]
    return {
        "base_identifier": best["base_identifier"],
        "name_pt": best["name_pt"],
        "name_en": best["name_en"],
        "category": best["category"],
        "slot_type": best["slot_type"]
    }


def generate_tier_equivalent_variants(base_identifier: str, target_equivalent: int) -> List[Dict[str, Any]]:
    """
    Gera todas as variantes de Tier e Encantamento que somam o tier equivalente alvo.
    Exemplo para target_equivalent = 7:
    - 4.3 (T4_BASE@3)
    - 5.2 (T5_BASE@2)
    - 6.1 (T6_BASE@1)
    - 7.0 (T7_BASE)
    """
    metadata_manager.ensure_data_loaded()
    variants = []

    # Tiers elegíveis: de T4 até min(8, target_equivalent)
    # Se o target for menor que 4 (ex: 3), inclui T3.
    min_tier = 3 if target_equivalent < 4 else 4
    max_tier = min(8, target_equivalent)

    for t in range(min_tier, max_tier + 1):
        enc = target_equivalent - t
        if 0 <= enc <= 4:
            item_id = f"T{t}_{base_identifier}@{enc}" if enc > 0 else f"T{t}_{base_identifier}"
            
            # Verifica se o item de fato existe no jogo
            if item_id in metadata_manager.item_names:
                name_pt = metadata_manager.get_item_name(item_id)
                name_en = metadata_manager.get_item_name_en(item_id)
                variants.append({
                    "item_id": item_id,
                    "tier": t,
                    "enchantment": enc,
                    "tier_enchant_label": f"{t}.{enc}",
                    "name_pt": name_pt,
                    "name_en": name_en,
                    "is_flat": (enc == 0 and t == target_equivalent),
                    "icon_url": metadata_manager.get_icon_url(item_id)
                })

    return variants


async def fetch_prices_for_variants(
    item_ids: List[str],
    city: str,
    price_mode: str = "live",
    server_region: str = "americas",
    max_quality: int = 2
) -> Dict[str, Dict[str, Any]]:
    """
    Busca preços consolidados por item_id na cidade especificada.
    Suporta:
    - 'live': menor sell_price_min ativo no mercado da cidade.
    - 'history': média de preços históricos diários no banco SQLite local.
    - 'databricks': média na tabela Gold Databricks (se configurado).
    """
    results: Dict[str, Dict[str, Any]] = {}
    city_clean = city.strip()

    # 1. Modo Databricks (se configurado e solicitado)
    if price_mode.lower() == "databricks" and databricks_client.is_configured():
        loc_id = CITY_TO_LOCATION_ID.get(city_clean.lower())
        db_res = await databricks_client.query_gold_features(
            item_ids=item_ids,
            location_id=loc_id,
            limit=len(item_ids) * 3
        )
        if db_res.get("success") and db_res.get("rows"):
            for row in db_res["rows"]:
                iid = row.get("item_id")
                q = int(row.get("quality_level") or 1)
                avg_p = int(row.get("avg_price") or 0)
                if q <= max_quality and avg_p > 0:
                    if iid not in results or avg_p < results[iid]["price"]:
                        results[iid] = {
                            "price": avg_p,
                            "source": "databricks_gold",
                            "quality": q,
                            "quality_name": QUALITY_NAMES.get(q, f"Q{q}"),
                            "buy_price_max": 0,
                            "sell_price_min": avg_p,
                            "in_stock": True
                        }
            if len(results) == len(item_ids):
                return results

    # 2. Modo Histórico Local (SQLite)
    if price_mode.lower() == "history":
        db_path = os.path.join(DATA_DIR, "market_history_americas.db")
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                placeholders = ",".join(["?"] * len(item_ids))
                query = f"""
                    SELECT item_id, quality, avg_historical_price, avg_daily_sales
                    FROM history_stats
                    WHERE item_id IN ({placeholders})
                      AND LOWER(location) = LOWER(?)
                      AND quality <= ?
                      AND avg_historical_price > 0
                    ORDER BY avg_historical_price ASC
                """
                params = list(item_ids) + [city_clean, max_quality]
                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                for row in rows:
                    iid, q, avg_p, sales = row
                    if iid not in results:
                        results[iid] = {
                            "price": int(avg_p),
                            "source": "sqlite_history",
                            "quality": q,
                            "quality_name": QUALITY_NAMES.get(q, f"Q{q}"),
                            "buy_price_max": 0,
                            "sell_price_min": int(avg_p),
                            "avg_daily_sales": float(sales),
                            "in_stock": True
                        }
                return results
            except Exception as e:
                logger.warning(f"Falha ao consultar SQLite history: {e}. Fallback para live.")

    # 3. Modo Live (AODP REST com Batching e Cache)
    qualities = list(range(1, max_quality + 1))
    raw_prices = await aodp_client.get_current_prices(
        item_ids=item_ids,
        locations=[city_clean],
        qualities=qualities,
        region=server_region
    )

    for entry in raw_prices:
        iid = entry.get("item_id")
        q = entry.get("quality", 1)
        sell_min = entry.get("sell_price_min", 0) or 0
        buy_max = entry.get("buy_price_max", 0) or 0
        loc = entry.get("city", "")

        if loc.lower() != city_clean.lower():
            continue

        if sell_min > 0:
            if iid not in results or sell_min < results[iid]["price"]:
                results[iid] = {
                    "price": sell_min,
                    "source": "aodp_live_sell_order",
                    "quality": q,
                    "quality_name": QUALITY_NAMES.get(q, f"Q{q}"),
                    "sell_price_min": sell_min,
                    "buy_price_max": buy_max,
                    "in_stock": True,
                    "updated_at": entry.get("sell_price_min_date")
                }
        elif buy_max > 0 and iid not in results:
            # Caso só tenha buy order ativa
            results[iid] = {
                "price": buy_max,
                "source": "aodp_live_buy_order_only",
                "quality": q,
                "quality_name": QUALITY_NAMES.get(q, f"Q{q}"),
                "sell_price_min": 0,
                "buy_price_max": buy_max,
                "in_stock": False,
                "updated_at": entry.get("buy_price_max_date")
            }

    return results


async def optimize_budget_build(
    items: List[str],
    target_tier_equivalent: int,
    city: str,
    price_mode: str = "live",
    server_region: str = "americas",
    max_quality: int = 2
) -> Dict[str, Any]:
    """
    Coordena a otimização de custo da build para o tier equivalente especificado.
    """
    if not items:
        return {"error": "A lista de itens não pode estar vazia."}

    if target_tier_equivalent < 4 or target_tier_equivalent > 9:
        return {"error": f"target_tier_equivalent ({target_tier_equivalent}) deve estar entre 4 e 9."}

    pieces_analysis = []
    all_needed_item_ids = set()
    unresolved_items = []

    # Passo 1: Resolução de famílias e geração de variantes
    for raw_item in items:
        family = resolve_item_family(raw_item)
        if not family:
            unresolved_items.append(raw_item)
            continue

        variants = generate_tier_equivalent_variants(family["base_identifier"], target_tier_equivalent)
        if not variants:
            unresolved_items.append(f"{raw_item} (sem variantes para T{target_tier_equivalent} eq)")
            continue

        for v in variants:
            all_needed_item_ids.add(v["item_id"])

        pieces_analysis.append({
            "original_query": raw_item,
            "base_identifier": family["base_identifier"],
            "name_pt": family["name_pt"],
            "name_en": family["name_en"],
            "category": family["category"],
            "slot_type": family["slot_type"],
            "variants": variants
        })

    if not pieces_analysis:
        return {
            "error": "Nenhum dos itens informados pôde ser identificado no catálogo.",
            "unresolved_items": unresolved_items
        }

    # Passo 2: Coleta de cotações em lote (1 única requisição HTTP)
    prices_map = await fetch_prices_for_variants(
        item_ids=list(all_needed_item_ids),
        city=city,
        price_mode=price_mode,
        server_region=server_region,
        max_quality=max_quality
    )

    # Passo 3: Avaliação financeira por peça e escolha da mais barata
    total_optimized_cost = 0
    total_flat_cost = 0
    pieces_result = []

    for piece in pieces_analysis:
        evaluated_variants = []
        cheapest_variant = None
        flat_variant = None

        for v in piece["variants"]:
            v_id = v["item_id"]
            price_info = prices_map.get(v_id)
            has_stock = bool(price_info and price_info.get("in_stock") and price_info.get("price", 0) > 0)
            price_val = price_info.get("price", 0) if price_info else 0
            qual_name = price_info.get("quality_name", "Normal") if price_info else "N/A"

            variant_entry = {
                "item_id": v_id,
                "tier_enchant": v["tier_enchant_label"],
                "name_pt": v["name_pt"],
                "price": price_val,
                "in_stock": has_stock,
                "quality": qual_name,
                "is_flat": v["is_flat"],
                "icon_url": v["icon_url"]
            }
            evaluated_variants.append(variant_entry)

            # Rastreia variante flat (ex: 7.0)
            if v["is_flat"]:
                flat_variant = variant_entry

            # Rastreia mais barata com estoque
            if has_stock:
                if cheapest_variant is None or price_val < cheapest_variant["price"]:
                    cheapest_variant = variant_entry

        # Se nenhuma tiver estoque ativo, escolhe a menor cotação disponível (ou primeira)
        if cheapest_variant is None and evaluated_variants:
            with_any_price = [ev for ev in evaluated_variants if ev["price"] > 0]
            if with_any_price:
                cheapest_variant = min(with_any_price, key=lambda x: x["price"])
            else:
                cheapest_variant = evaluated_variants[0]

        # Calcula economia individual contra o modelo flat
        savings_vs_flat = 0
        savings_vs_flat_pct = 0.0
        if flat_variant and flat_variant["price"] > 0 and cheapest_variant["price"] > 0:
            savings_vs_flat = flat_variant["price"] - cheapest_variant["price"]
            savings_vs_flat_pct = round((savings_vs_flat / flat_variant["price"]) * 100, 1)

        total_optimized_cost += cheapest_variant["price"]
        if flat_variant and flat_variant["price"] > 0:
            total_flat_cost += flat_variant["price"]
        else:
            total_flat_cost += cheapest_variant["price"]

        # Ordena variantes por preço (menor primeiro, zerados/sem estoque no fim)
        evaluated_variants.sort(
            key=lambda x: (not x["in_stock"], x["price"] == 0, x["price"])
        )

        pieces_result.append({
            "slot_type": piece["slot_type"],
            "base_name_pt": piece["name_pt"],
            "recommended": {
                "item_id": cheapest_variant["item_id"],
                "tier_enchant": cheapest_variant["tier_enchant"],
                "name_pt": cheapest_variant["name_pt"],
                "price": cheapest_variant["price"],
                "in_stock": cheapest_variant["in_stock"],
                "quality": cheapest_variant["quality"],
                "savings_vs_flat": savings_vs_flat,
                "savings_vs_flat_pct": savings_vs_flat_pct
            },
            "flat_reference": {
                "item_id": flat_variant["item_id"] if flat_variant else None,
                "tier_enchant": flat_variant["tier_enchant"] if flat_variant else None,
                "price": flat_variant["price"] if flat_variant else 0,
                "in_stock": flat_variant["in_stock"] if flat_variant else False
            } if flat_variant else None,
            "all_equivalent_options": evaluated_variants
        })

    total_savings_silver = max(0, total_flat_cost - total_optimized_cost)
    total_savings_pct = (
        round((total_savings_silver / total_flat_cost) * 100, 1)
        if total_flat_cost > 0 else 0.0
    )

    return {
        "city": city,
        "server_region": server_region,
        "target_tier_equivalent": target_tier_equivalent,
        "price_mode": price_mode,
        "summary": {
            "total_optimized_cost": total_optimized_cost,
            "total_flat_cost": total_flat_cost,
            "total_savings_silver": total_savings_silver,
            "total_savings_pct": total_savings_pct,
            "total_pieces": len(pieces_result),
            "unresolved_items": unresolved_items
        },
        "build_pieces": pieces_result
    }
