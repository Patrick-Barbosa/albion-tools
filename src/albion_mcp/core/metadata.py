"""
Gerenciador de Metadados, Itens e Traduções (PT-BR / EN) para Albion Online.
"""

import json
import os
import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("albion_mcp.metadata")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_DIR = os.path.join(REPO_ROOT, "data")
ITEMS_FILE = os.path.join(DATA_DIR, "items.json")

QUALITY_NAMES = {
    1: "Normal",
    2: "Bom",
    3: "Notável",
    4: "Excelente",
    5: "Obra-prima"
}

QUALITY_NAMES_REVERSE = {
    "normal": 1,
    "bom": 2,
    "notavel": 3,
    "notável": 3,
    "excelente": 4,
    "obra-prima": 5,
    "obra prima": 5
}

CITIES = [
    "Bridgewatch",
    "Lymhurst",
    "Fort Sterling",
    "Martlock",
    "Thetford",
    "Brecilien",
    "Caerleon",
    "Black Market"
]

SAFE_ROYAL_CITIES = ["Bridgewatch", "Fort Sterling", "Lymhurst", "Martlock", "Thetford"]

CATEGORIES = [
    "Armas",
    "Armaduras",
    "Bolsas & Capas",
    "Consumíveis",
    "Recursos Refinados",
    "Materiais de Encanto",
    "Secundários"
]

TIERS = ["T2", "T3", "T4", "T5", "T6", "T7", "T8"]

# Mapeamento de materiais consumidos por nível de encantamento (.1, .2, .3)
ENCHANT_COST_MAP = {
    "2H_WEAPON": 384,
    "1H_WEAPON": 288,
    "ARMOR": 192,
    "BAG": 192,
    "HELMET": 96,
    "BOOTS": 96,
    "OFFHAND": 96,
    "CAPE": 96,
}


class ItemMetadataManager:
    def __init__(self):
        self.item_names: Dict[str, str] = {}
        self.item_names_en: Dict[str, str] = {}
        self._items_catalog: List[Dict[str, Any]] = []
        self._is_loaded = False

    def ensure_data_loaded(self):
        if self._is_loaded and len(self.item_names) > 0:
            return

        if os.path.exists(ITEMS_FILE):
            try:
                with open(ITEMS_FILE, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    self._parse_items_json(raw_data)
                    self._is_loaded = True
                    logger.info(f"Carregados {len(self.item_names)} itens dos metadados.")
                    return
            except Exception as e:
                logger.warning(f"Falha ao ler cache de itens em {ITEMS_FILE}: {e}")

        self._is_loaded = True

    def _parse_items_json(self, raw_data: list):
        for item in raw_data:
            unique_name = item.get("UniqueName")
            if not unique_name:
                continue
            loc_names = item.get("LocalizedNames") or {}
            pt_name = loc_names.get("PT-BR")
            en_name = loc_names.get("EN-US") or unique_name
            name = pt_name or en_name or unique_name

            self.item_names[unique_name] = name
            self.item_names_en[unique_name] = en_name

    def get_item_name(self, raw_id: str) -> str:
        self.ensure_data_loaded()
        base_id = raw_id.split("@")[0]
        enchantment = self.get_enchantment_level(raw_id)

        name = self.item_names.get(raw_id)
        if not name:
            name = self.item_names.get(base_id)

        if not name:
            cleaned = base_id
            for prefix in ["T4_", "T5_", "T6_", "T7_", "T8_", "T1_", "T2_", "T3_"]:
                if cleaned.startswith(prefix):
                    cleaned = cleaned[len(prefix):]
                    break
            name = f"{self.get_tier(raw_id)} {cleaned.replace('_', ' ').title()}"

        if enchantment > 0 and not ("." in name or "@" in name):
            name = f"{name} .{enchantment}"

        return name

    def get_item_name_en(self, raw_id: str) -> str:
        self.ensure_data_loaded()
        base_id = raw_id.split("@")[0]
        return self.item_names_en.get(raw_id) or self.item_names_en.get(base_id) or base_id

    @staticmethod
    def get_tier(item_id: str) -> str:
        match = re.match(r"^(T\d)", item_id)
        return match.group(1) if match else "T4"

    @staticmethod
    def get_enchantment_level(item_id: str) -> int:
        if "@" in item_id:
            try:
                return int(item_id.split("@")[1])
            except ValueError:
                return 0
        return 0

    @staticmethod
    def get_icon_url(item_id: str, quality: int = 1) -> str:
        return f"https://render.albiononline.com/v1/item/{item_id}.png?quality={quality}"

    def get_slot_type(self, item_id: str) -> str:
        """Determina o slot do equipamento para cálculo exato de consumo de insumos."""
        base = item_id.split("@")[0].upper()
        if "BAG" in base:
            return "BAG"
        if "CAPE" in base:
            return "CAPE"
        if "ARMOR" in base or "ROBE" in base or "JACKET" in base or "_CLOTH" in base or "_LEATHER" in base or "_PLATE" in base:
            if "HEAD" in base or "COWl" in base or "HOOD" in base or "HELMET" in base:
                return "HELMET"
            if "SHOES" in base or "BOOTS" in base or "SANDALS" in base:
                return "BOOTS"
            return "ARMOR"
        if "HEAD" in base or "COWL" in base or "HOOD" in base or "HELMET" in base:
            return "HELMET"
        if "SHOES" in base or "BOOTS" in base or "SANDALS" in base:
            return "BOOTS"
        if "OFF_" in base or "SHIELD" in base or "TORCH" in base or "BOOK" in base or "HORN" in base:
            return "OFFHAND"
        # 2H vs 1H armas
        two_handed_keywords = [
            "2H", "GREATSWORD", "GREATAXE", "HALBERD", "LONGBOW", "WARBOW",
            "CROSSBOW_HEAVY", "POLESTAFF", "QUARTERSTAFF", "SPEAR_TWOHANDED",
            "GLAIVE", "DOUBLEBLADED", "HAMMER_TWOHANDED", "CROSSBOW"
        ]
        for kw in two_handed_keywords:
            if kw in base:
                return "2H_WEAPON"

        return "1H_WEAPON"

    def get_enchantment_cost(self, item_id: str) -> int:
        """Retorna o número de runas/almas/relíquias necessárias por nível (.1, .2, .3)."""
        slot = self.get_slot_type(item_id)
        return ENCHANT_COST_MAP.get(slot, 192)

    def get_category_for_item(self, item_id: str) -> str:
        base = item_id.split("@")[0].upper()
        if "BAG" in base or "CAPE" in base:
            return "Bolsas & Capas"
        if "RUNE" in base or "SOUL" in base or "RELIC" in base:
            return "Materiais de Encanto"
        if "POTION" in base or "MEAL" in base or "FISH" in base:
            return "Consumíveis"
        if "ARMOR" in base or "HEAD" in base or "SHOES" in base or "ROBE" in base or "JACKET" in base or "COWL" in base or "BOOTS" in base:
            return "Armaduras"
        if ("WEAPON" in base or "STAFF" in base or "BOW" in base or "SWORD" in base or "AXE" in base
                or "DAGGER" in base or "SPEAR" in base or "CROSSBOW" in base or "HAMMER" in base
                or "MACE" in base or "GLAIVE" in base or "CURSED" in base or "FIRE" in base
                or "FROST" in base or "HOLY" in base or "ARCANE" in base or "NATURE" in base):
            return "Armas"
        if "OFF_" in base or "SHIELD" in base or "TORCH" in base or "BOOK" in base or "HORN" in base:
            return "Secundários"
        if "PLANKS" in base or "LEATHER" in base or "METALBAR" in base or "CLOTH" in base or "STONEBLOCK" in base or "ORE" in base or "HIDE" in base or "WOOD" in base or "FIBER" in base or "ROCK" in base:
            return "Recursos Refinados"
        return "Secundários"

    def search_items(
        self,
        query: str,
        tier: Optional[str] = None,
        category: Optional[str] = None,
        enchantment: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Busca itens com filtros avançados."""
        self.ensure_data_loaded()
        q_lower = query.lower().strip() if query else ""
        results = []

        for item_id, pt_name in self.item_names.items():
            en_name = self.item_names_en.get(item_id, "")
            
            # Filtro de texto
            if q_lower:
                if (q_lower not in item_id.lower() and
                    q_lower not in pt_name.lower() and
                    q_lower not in en_name.lower()):
                    continue

            # Filtro de Tier
            item_tier = self.get_tier(item_id)
            if tier and tier.upper() != "ALL" and item_tier != tier.upper():
                continue

            # Filtro de Encantamento
            item_enc = self.get_enchantment_level(item_id)
            if enchantment is not None and item_enc != enchantment:
                continue

            # Filtro de Categoria
            item_cat = self.get_category_for_item(item_id)
            if category and category.lower() != "all" and item_cat.lower() != category.lower():
                continue

            slot = self.get_slot_type(item_id)
            enc_cost = self.get_enchantment_cost(item_id)

            results.append({
                "item_id": item_id,
                "name_pt": pt_name,
                "name_en": en_name,
                "tier": item_tier,
                "enchantment": item_enc,
                "category": item_cat,
                "slot_type": slot,
                "enchant_material_cost_per_level": enc_cost,
                "icon_url": self.get_icon_url(item_id)
            })

            if len(results) >= limit:
                break

        return results


# Instância global
metadata_manager = ItemMetadataManager()
