"""
Motor Universal de Otimização de Carga e Montarias (Loadout Solver) para Albion Online.

Calcula a capacidade efetiva exata com efeitos multiplicadores sinérgicos
(Montaria + Bolsa + Base) * (1 + %Torta) * (1 + %Bota) e resolve a combinação
mais barata em prata para transportar qualquer volume de carga.
"""

from typing import Dict, Any, List, Optional
import math

PLAYER_BASE_CAPACITY_KG = 50.0

MOUNTS_CATALOG = {
    "T5_BOAR": {
        "name": "Javali T5",
        "tier": 5,
        "base_capacity_kg": 750.0,
        "cost_silver": 65000,
        "gallop_speed_mult": 1.05,
        "is_passive": True,
        "description": "Carga passiva segura contra desmonte. Ideal para fardos médios de facção."
    },
    "T7_BOAR": {
        "name": "Javali Selvagem T7",
        "tier": 7,
        "base_capacity_kg": 1100.0,
        "cost_silver": 350000,
        "gallop_speed_mult": 1.15,
        "is_passive": True,
        "description": "Excelente velocidade, armadura e carga passiva embutida."
    },
    "T8_GRIZZLY": {
        "name": "Urso Cinzento T8",
        "tier": 8,
        "base_capacity_kg": 2000.0,
        "cost_silver": 1800000,
        "gallop_speed_mult": 1.00,
        "is_passive": True,
        "description": "Tanque supremo anti-gank para transporte pesado com carga passiva."
    },
    "T4_OX": {
        "name": "Boi de Transporte T4",
        "tier": 4,
        "base_capacity_kg": 800.0,
        "cost_silver": 22000,
        "gallop_speed_mult": 0.75,
        "is_passive": True,
        "description": "Transporte básico e barato com carga passiva."
    },
    "T5_OX": {
        "name": "Boi de Transporte T5",
        "tier": 5,
        "base_capacity_kg": 1400.0,
        "cost_silver": 55000,
        "gallop_speed_mult": 0.75,
        "is_passive": True,
        "description": "Padrão industrial de carga regional."
    },
    "T6_OX": {
        "name": "Boi de Transporte T6",
        "tier": 6,
        "base_capacity_kg": 2100.0,
        "cost_silver": 130000,
        "gallop_speed_mult": 0.75,
        "is_passive": True,
        "description": "Carga pesada intercidades. Suporta fardo de 15 corações puro."
    },
    "T7_OX": {
        "name": "Boi de Transporte T7",
        "tier": 7,
        "base_capacity_kg": 2700.0,
        "cost_silver": 300000,
        "gallop_speed_mult": 0.75,
        "is_passive": True,
        "description": "Grande porte para transporte intercidades volumoso."
    },
    "T8_OX": {
        "name": "Boi de Transporte T8",
        "tier": 8,
        "base_capacity_kg": 3500.0,
        "cost_silver": 650000,
        "gallop_speed_mult": 0.75,
        "is_passive": True,
        "description": "Porte máximo padrão em boi."
    },
    "T8_MAMMOTH": {
        "name": "Mamute de Transporte T8",
        "tier": 8,
        "base_capacity_kg": 25000.0,
        "cost_silver": 125000000,
        "gallop_speed_mult": 0.55,
        "is_passive": True,
        "description": "Transporte industrial em massa."
    },
    "T4_HORSE": {
        "name": "Cavalo com Bolsa T4",
        "tier": 4,
        "base_capacity_kg": 250.0,
        "cost_silver": 15000,
        "gallop_speed_mult": 1.10,
        "is_passive": False,
        "description": "Carga ativa. Risco de imobilização se desmontado em perigo."
    },
    "T5_HORSE": {
        "name": "Cavalo com Bolsa T5",
        "tier": 5,
        "base_capacity_kg": 400.0,
        "cost_silver": 25000,
        "gallop_speed_mult": 1.15,
        "is_passive": False,
        "description": "Carga ativa rápida para cargas leves."
    },
    "T5_SWIFTCLAW": {
        "name": "Garra-ligeira T5",
        "tier": 5,
        "base_capacity_kg": 150.0,
        "cost_silver": 110000,
        "gallop_speed_mult": 1.25,
        "is_passive": False,
        "description": "Velocidade máxima para carga leve (3 corações com bolsa)."
    }
}

BAGS_CATALOG = {
    "NONE": {"name": "Sem Bolsa", "bonus_kg": 0.0, "cost_silver": 0},
    "T4_BAG": {"name": "Bolsa T4.0", "bonus_kg": 86.0, "cost_silver": 3500},
    "T4_BAG_1": {"name": "Bolsa T4.1", "bonus_kg": 110.0, "cost_silver": 8000},
    "T5_BAG": {"name": "Bolsa T5.0", "bonus_kg": 141.0, "cost_silver": 12000},
    "T5_BAG_1": {"name": "Bolsa T5.1", "bonus_kg": 180.0, "cost_silver": 25000},
    "T6_BAG": {"name": "Bolsa T6.0", "bonus_kg": 230.0, "cost_silver": 45000},
    "T6_BAG_1": {"name": "Bolsa T6.1", "bonus_kg": 295.0, "cost_silver": 90000},
    "T7_BAG": {"name": "Bolsa T7.0", "bonus_kg": 377.0, "cost_silver": 160000},
    "T8_BAG": {"name": "Bolsa T8.0", "bonus_kg": 617.0, "cost_silver": 450000},
}

FOOD_CATALOG = {
    "NONE": {"name": "Sem Comida", "bonus_pct": 0.0, "cost_silver": 0},
    "T3_PIE": {"name": "Torta de Galinha T3", "bonus_pct": 10.0, "cost_silver": 1500},
    "T5_PIE": {"name": "Torta de Ganso T5", "bonus_pct": 20.0, "cost_silver": 3000},
    "T7_PIE": {"name": "Torta de Porco T7", "bonus_pct": 30.0, "cost_silver": 5500},
    "T7_PIE_1": {"name": "Torta de Porco T7.1", "bonus_pct": 34.5, "cost_silver": 12000},
}

BOOTS_CATALOG = {
    "TRANSPORT_14": {"name": "Passiva Transportador (14%)", "bonus_pct": 14.0, "cost_silver": 0},
    "TRANSPORT_10": {"name": "Passiva Transportador (10%)", "bonus_pct": 10.0, "cost_silver": 0},
    "NONE": {"name": "Sem Passiva de Bota", "bonus_pct": 0.0, "cost_silver": 0},
}

# Mapeamentos consolidados para interoperabilidade universal com polars_analytics e anti_hallucination
MOUNTS_LIST = [
    {"id": "HORSE_T4", "name": "Cavalo com Bolsa T4", "tier": "T4", "capacity_kg": 250, "est_cost": 15000, "is_passive": False},
    {"id": "HORSE_T5", "name": "Cavalo com Bolsa T5", "tier": "T5", "capacity_kg": 400, "est_cost": 25000, "is_passive": False},
    {"id": "T5_BOAR", "name": "Javali T5", "tier": "T5", "capacity_kg": 750, "est_cost": 65000, "is_passive": True},
    {"id": "OX_T4", "name": "Boi de Transporte T4 (Adepto)", "tier": "T4", "capacity_kg": 800, "est_cost": 22000, "is_passive": True},
    {"id": "T7_BOAR", "name": "Javali Selvagem T7", "tier": "T7", "capacity_kg": 1100, "est_cost": 350000, "is_passive": True},
    {"id": "OX_T5", "name": "Boi de Transporte T5 (Perito)", "tier": "T5", "capacity_kg": 1400, "est_cost": 55000, "is_passive": True},
    {"id": "T8_GRIZZLY", "name": "Urso Cinzento T8", "tier": "T8", "capacity_kg": 2000, "est_cost": 1800000, "is_passive": True},
    {"id": "OX_T6", "name": "Boi de Transporte T6 (Mestre)", "tier": "T6", "capacity_kg": 2100, "est_cost": 130000, "is_passive": True},
    {"id": "OX_T7", "name": "Boi de Transporte T7 (Grão-Mestre)", "tier": "T7", "capacity_kg": 2700, "est_cost": 300000, "is_passive": True},
    {"id": "OX_T8", "name": "Boi de Transporte T8 (Ancião)", "tier": "T8", "capacity_kg": 3500, "est_cost": 650000, "is_passive": True},
    {"id": "MAMMOTH_T8", "name": "Mamute de Transporte T8", "tier": "T8", "capacity_kg": 25000, "est_cost": 125000000, "is_passive": True},
]

BAG_LOAD_MAP = {
    "NONE": {"name": "Sem Bolsa", "bonus_kg": 0, "est_cost": 0},
    "T4.0": {"name": "Bolsa T4.0", "bonus_kg": 86, "est_cost": 3500},
    "T4.1": {"name": "Bolsa T4.1", "bonus_kg": 110, "est_cost": 8000},
    "T5.0": {"name": "Bolsa T5.0", "bonus_kg": 141, "est_cost": 12000},
    "T5.1": {"name": "Bolsa T5.1", "bonus_kg": 180, "est_cost": 25000},
    "T6.0": {"name": "Bolsa T6.0", "bonus_kg": 230, "est_cost": 45000},
    "T6.1": {"name": "Bolsa T6.1", "bonus_kg": 295, "est_cost": 90000},
    "T7.0": {"name": "Bolsa T7.0", "bonus_kg": 377, "est_cost": 160000},
    "T8.0": {"name": "Bolsa T8.0", "bonus_kg": 617, "est_cost": 450000},
}

PIE_LOAD_MAP = {
    "NONE": {"name": "Sem Comida", "bonus_pct": 0.0, "est_cost": 0},
    "T3_CHICKEN": {"name": "Torta de Galinha T3 (+10%)", "bonus_pct": 10.0, "est_cost": 1500},
    "T5_GOOSE": {"name": "Torta de Ganso T5 (+20%)", "bonus_pct": 20.0, "est_cost": 3000},
    "T7_PORK": {"name": "Torta de Porco T7 (+30%)", "bonus_pct": 30.0, "est_cost": 5500},
    "T7.1_PORK": {"name": "Torta de Porco T7.1 (+34.5%)", "bonus_pct": 34.5, "est_cost": 12000},
}

BOOTS_PASSIVE_MAP = {
    "NONE": {"name": "Sem Passiva", "bonus_pct": 0.0},
    "COURIER_STANDARD": {"name": "Passiva Transportador (+14%)", "bonus_pct": 14.0},
    "COURIER_BASIC": {"name": "Passiva Transportador Básica (+10%)", "bonus_pct": 10.0},
}


def calculate_effective_capacity(
    mount_capacity_kg: float,
    bag_bonus_kg: float = 0.0,
    pie_bonus_pct: float = 0.0,
    boots_bonus_pct: float = 14.0,
    player_base_kg: float = PLAYER_BASE_CAPACITY_KG
) -> float:
    """
    Fórmula oficial com efeitos sinérgicos multiplicativos:
    Capacidade = (Montaria + Bolsa + 50) * (1 + Torta/100) * (1 + Bota/100)
    """
    base_sum = mount_capacity_kg + bag_bonus_kg + player_base_kg
    pie_mult = 1.0 + (pie_bonus_pct / 100.0)
    boots_mult = 1.0 + (boots_bonus_pct / 100.0)
    return round(base_sum * pie_mult * boots_mult, 1)


def solve_cheapest_loadout(
    target_weight_kg: float,
    current_mount_id: Optional[str] = None,
    risk_level: str = "SAFE_ONLY",
    max_budget: Optional[int] = None
) -> Dict[str, Any]:
    """
    Solver Combinatório de Menor Custo:
    Encontra a combinação mais barata de (Montaria + Bolsa + Torta + Bota)
    que satisfaça Capacidade Efetiva >= target_weight_kg com Uso <= 100%.

    Parâmetros:
    - target_weight_kg: Peso alvo a ser transportado em kg.
    - current_mount_id: ID da montaria que o jogador já possui (ex: 'T5_BOAR').
    - risk_level: 'SAFE_ONLY' ou 'ALLOW_RED_ZONE'. Em Red Zone, descarta montarias de carga ativa.
    - max_budget: Limite de prata que o jogador pode gastar (opcional).
    """
    # 1. Normalização e validação de montaria existente
    current_mount_normalized = None
    if current_mount_id:
        norm = current_mount_id.upper().strip()
        # Tratamento de aliases comuns
        if norm in ("JAVALI", "JAVALI_T5", "BOAR", "BOAR_T5", "T5_BOAR"):
            norm = "T5_BOAR"
        elif norm in ("BOI_T4", "T4_OX"):
            norm = "T4_OX"
        elif norm in ("BOI_T5", "T5_OX"):
            norm = "T5_OX"
        elif norm in ("BOI_T6", "T6_OX"):
            norm = "T6_OX"
        if norm in MOUNTS_CATALOG:
            current_mount_normalized = norm

    # 2. Avaliação se a montaria atual do jogador (com complementos baratos) resolve
    current_mount_eval = None
    if current_mount_normalized:
        m_info = MOUNTS_CATALOG[current_mount_normalized]
        # Testa se a montaria atual com torta e bolsa aguenta
        best_with_current = None
        for b_id, b_info in BAGS_CATALOG.items():
            for p_id, p_info in FOOD_CATALOG.items():
                cap = calculate_effective_capacity(
                    mount_capacity_kg=m_info["base_capacity_kg"],
                    bag_bonus_kg=b_info["bonus_kg"],
                    pie_bonus_pct=p_info["bonus_pct"],
                    boots_bonus_pct=14.0
                )
                if cap >= target_weight_kg:
                    cost = b_info["cost_silver"] + p_info["cost_silver"]
                    if best_with_current is None or cost < best_with_current["additional_investment_silver"]:
                        best_with_current = {
                            "mount_id": current_mount_normalized,
                            "mount_name": m_info["name"],
                            "bag_id": b_id,
                            "bag_name": b_info["name"],
                            "food_id": p_id,
                            "food_name": p_info["name"],
                            "boots_passive": "Passiva Transportador (14%)",
                            "effective_capacity_kg": cap,
                            "total_capacity_kg": cap,
                            "usage_pct": round((target_weight_kg / cap) * 100, 1),
                            "additional_investment_silver": cost,
                            "mount_already_owned": True,
                            "is_passive": m_info["is_passive"]
                        }
        current_mount_eval = best_with_current

    # 3. Solver Global: Varredura de todo o espaço combinatório
    valid_combos = []

    for m_id, m_info in MOUNTS_CATALOG.items():
        # Restrição de Red Zone: descarta montarias sem carga passiva
        if risk_level == "ALLOW_RED_ZONE" and not m_info["is_passive"]:
            continue

        mount_cost = 0 if (current_mount_normalized and m_id == current_mount_normalized) else m_info["cost_silver"]

        for b_id, b_info in BAGS_CATALOG.items():
            for p_id, p_info in FOOD_CATALOG.items():
                cap = calculate_effective_capacity(
                    mount_capacity_kg=m_info["base_capacity_kg"],
                    bag_bonus_kg=b_info["bonus_kg"],
                    pie_bonus_pct=p_info["bonus_pct"],
                    boots_bonus_pct=14.0
                )

                if cap >= target_weight_kg:
                    total_cost = mount_cost + b_info["cost_silver"] + p_info["cost_silver"]
                    if max_budget is not None and total_cost > max_budget:
                        continue

                    usage_pct = round((target_weight_kg / cap) * 100, 1)

                    valid_combos.append({
                        "mount_id": m_id,
                        "mount_name": m_info["name"],
                        "mount_tier": m_info["tier"],
                        "mount_is_passive": m_info["is_passive"],
                        "bag_id": b_id,
                        "bag_name": b_info["name"],
                        "food_id": p_id,
                        "food_name": p_info["name"],
                        "boots_passive": "Passiva Transportador (14%)",
                        "effective_capacity_kg": cap,
                        "total_capacity_kg": cap,
                        "usage_pct": usage_pct,
                        "total_cost_silver": total_cost,
                        "mount_cost_silver": mount_cost,
                        "mount_already_owned": (current_mount_normalized == m_id)
                    })


    if not valid_combos:
        return {
            "status": "INSUFFICIENT_CAPACITY_OR_BUDGET",
            "message": f"Não foi possível encontrar uma combinação viável para {target_weight_kg} kg dentro das restrições.",
            "target_weight_kg": target_weight_kg,
            "risk_level": risk_level,
            "current_mount_eval": current_mount_eval
        }

    # Ordena por: 1) Menor custo total em prata, 2) Menor % de uso (maior folga de segurança)
    valid_combos.sort(key=lambda x: (x["total_cost_silver"], x["usage_pct"]))
    cheapest_combo = valid_combos[0]

    # 4. Cálculo de economia comparativa
    # Acha qual boi puro (sem bolsa/torta) seria necessário
    naive_mount_cost = 0
    naive_mount_name = "Nenhum"
    for m_id, m_info in sorted(MOUNTS_CATALOG.items(), key=lambda x: x[1]["base_capacity_kg"]):
        if m_info["base_capacity_kg"] + PLAYER_BASE_CAPACITY_KG >= target_weight_kg:
            naive_mount_cost = m_info["cost_silver"]
            naive_mount_name = m_info["name"]
            break

    silver_saved = max(0, naive_mount_cost - cheapest_combo["total_cost_silver"])

    return {
        "status": "SUCCESS",
        "target_weight_kg": target_weight_kg,
        "risk_level": risk_level,
        "cheapest_loadout": cheapest_combo,
        "current_mount_solution": current_mount_eval,
        "is_current_mount_sufficient": current_mount_eval is not None,
        "silver_saved_vs_naive_mount": silver_saved,
        "naive_pure_mount_comparison": {
            "mount_name": naive_mount_name,
            "cost_silver": naive_mount_cost
        },
        "all_viable_combos_count": len(valid_combos)
    }
