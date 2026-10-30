"""
Busca e ficha técnica de itens no catálogo local (PT-BR / EN).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .metadata import metadata_manager


def search_items(
    query: str,
    tier: Optional[str] = None,
    category: Optional[str] = None,
    enchantment: Optional[int] = None,
    limit: int = 15,
) -> Dict[str, Any]:
    """Busca itens por nome (PT-BR/EN) ou Item ID, com filtros opcionais."""
    results = metadata_manager.search_items(
        query=query,
        tier=tier,
        category=category,
        enchantment=enchantment,
        limit=limit,
    )
    return {"query": query, "total_found": len(results), "items": results}


def item_details(item_id: str) -> Dict[str, Any]:
    """Ficha completa: nomes, tier, encantamento, slot, insumos de encantamento e ícone."""
    metadata_manager.ensure_data_loaded()

    base_id = item_id.split("@")[0]
    if base_id not in metadata_manager.item_names:
        return {"error": f"Item '{item_id}' não encontrado no catálogo.", "item_id": item_id}

    name_pt = metadata_manager.get_item_name(item_id)
    name_en = metadata_manager.get_item_name_en(item_id)
    tier = metadata_manager.get_tier(item_id)
    enchantment = metadata_manager.get_enchantment_level(item_id)
    materials = metadata_manager.get_enchantment_cost(item_id)

    return {
        "item_id": item_id,
        "name_pt": name_pt,
        "name_en": name_en,
        "tier": tier,
        "enchantment": enchantment,
        "category": metadata_manager.get_category_for_item(item_id),
        "slot_type": metadata_manager.get_slot_type(item_id),
        "enchant_materials_per_level": materials,
        "enchantment_rules": {
            ".0_to_.1": f"Requer {materials} Runas ({tier})",
            ".1_to_.2": f"Requer {materials} Almas ({tier})",
            ".2_to_.3": f"Requer {materials} Relíquias ({tier})",
        },
        "icon_url": metadata_manager.get_icon_url(item_id),
    }


def resolve_universe(
    category: Optional[str] = None,
    tier: Optional[str] = None,
    limit: int = 120,
) -> List[str]:
    """Lista de item_ids para varreduras em lote (Pareto, arbitragem)."""
    metadata_manager.ensure_data_loaded()

    ids = []
    for item_id in metadata_manager.item_names:
        if "@" in item_id:
            continue
        if category and metadata_manager.get_category_for_item(item_id) != category:
            continue
        if tier and metadata_manager.get_tier(item_id) != tier.upper():
            continue
        ids.append(item_id)

    return sorted(ids)[:limit]
