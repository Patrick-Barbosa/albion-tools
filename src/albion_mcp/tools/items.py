"""
Ferramentas MCP para busca e inspeção de itens e metadados.
"""

from typing import List, Dict, Any, Optional
from ..core.metadata import metadata_manager, QUALITY_NAMES, CATEGORIES, TIERS


def albion_search_items(
    query: str,
    tier: Optional[str] = None,
    category: Optional[str] = None,
    enchantment: Optional[int] = None,
    limit: int = 15
) -> Dict[str, Any]:
    """
    Busca itens no catálogo do Albion Online pelo nome em Português (PT-BR), Inglês ou Item ID.
    
    Parâmetros:
    - query: Termo de busca (ex: 'Espadão', 'Bolsa', 'T4_BAG', 'Peitoral de Soldado').
    - tier: Filtro opcional por Tier (ex: 'T4', 'T5', 'T6', 'T7', 'T8').
    - category: Filtro opcional por Categoria (ex: 'Armas', 'Armaduras', 'Bolsas & Capas', 'Recursos Refinados').
    - enchantment: Nível de encantamento (0 para plano, 1 para .1, 2 para .2, 3 para .3, 4 para .4).
    - limit: Limite de resultados retornados (padrão: 15).
    """
    results = metadata_manager.search_items(
        query=query,
        tier=tier,
        category=category,
        enchantment=enchantment,
        limit=limit
    )
    return {
        "query": query,
        "total_found": len(results),
        "items": results
    }


def albion_get_item_details(item_id: str) -> Dict[str, Any]:
    """
    Retorna a ficha técnica completa de um item:
    - Nomes oficiais em Português (PT-BR) e Inglês (EN-US).
    - Tier e Nível de Encantamento.
    - Categoria e Slot (Arma 2H, Arma 1H, Peitoral, Elmo, Bota, Bolsa, Capa, Secundário).
    - Custo exato em insumos para encantamento (.1, .2, .3) conforme múltiplos de 96.
    - URL oficial do ícone renderizado.
    """
    metadata_manager.ensure_data_loaded()
    name_pt = metadata_manager.get_item_name(item_id)
    name_en = metadata_manager.get_item_name_en(item_id)
    tier = metadata_manager.get_tier(item_id)
    enchantment = metadata_manager.get_enchantment_level(item_id)
    category = metadata_manager.get_category_for_item(item_id)
    slot_type = metadata_manager.get_slot_type(item_id)
    enchant_materials_cost = metadata_manager.get_enchantment_cost(item_id)
    icon_url = metadata_manager.get_icon_url(item_id)

    return {
        "item_id": item_id,
        "name_pt": name_pt,
        "name_en": name_en,
        "tier": tier,
        "enchantment": enchantment,
        "category": category,
        "slot_type": slot_type,
        "enchant_materials_per_level": enchant_materials_cost,
        "enchantment_rules": {
            ".0_to_.1": f"Requer {enchant_materials_cost} Runas ({tier})",
            ".1_to_.2": f"Requer {enchant_materials_cost} Almas ({tier})",
            ".2_to_.3": f"Requer {enchant_materials_cost} Relíquias ({tier})"
        },
        "icon_url": icon_url
    }
