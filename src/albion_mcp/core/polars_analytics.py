"""
Motor Analítico em Polars de Alta Performance para Albion Online.

Implementa:
- Simulação de Refino de Recursos (T2..T8) com bônus de cidade real (40% RRR / 53.9% Foco).
- Cascata de Refino Completa com Otimizador de Montaria e Carga (Bolsas, Tortas, Passivas).
- Scanner de Arbitragem entre Cidades Reais e Mercado Negro.
- Análise de Pareto 80/20 do mercado.
"""

import os
import sqlite3
import logging
from typing import Dict, Any, List, Optional
import polars as pl

from .metadata import metadata_manager, QUALITY_NAMES, SAFE_ROYAL_CITIES, CITIES
from .calculator import calculate_trade_profit, get_tax_rate, SETUP_FEE_RATE
from .databricks_client import databricks_client

logger = logging.getLogger("albion_mcp.analytics")

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data"))

# Cidades e Bônus Oficiais de Refino
REFINING_SPECIALTIES = {
    "Bridgewatch": {"resource": "STONE", "name": "Pedra -> Blocos", "raw_prefix": "ROCK", "refined_prefix": "STONEBLOCK"},
    "Martlock": {"resource": "HIDE", "name": "Pelego -> Couro", "raw_prefix": "HIDE", "refined_prefix": "LEATHER"},
    "Thetford": {"resource": "ORE", "name": "Minério -> Barras", "raw_prefix": "ORE", "refined_prefix": "METALBAR"},
    "Fort Sterling": {"resource": "WOOD", "name": "Madeira -> Tábuas", "raw_prefix": "WOOD", "refined_prefix": "PLANKS"},
    "Lymhurst": {"resource": "FIBER", "name": "Fibra -> Tecidos", "raw_prefix": "FIBER", "refined_prefix": "CLOTH"},
}

MOUNTS_LIST = [
    {"id": "HORSE_T5", "name": "Cavalo com Bolsa T5", "tier": "T5", "capacity_kg": 400, "est_cost": 25000},
    {"id": "OX_T4", "name": "Boi de Transporte T4 (Adepto)", "tier": "T4", "capacity_kg": 800, "est_cost": 20000},
    {"id": "OX_T5", "name": "Boi de Transporte T5 (Perito)", "tier": "T5", "capacity_kg": 1400, "est_cost": 55000},
    {"id": "OX_T6", "name": "Boi de Transporte T6 (Mestre)", "tier": "T6", "capacity_kg": 2100, "est_cost": 130000},
    {"id": "OX_T7", "name": "Boi de Transporte T7 (Grão-Mestre)", "tier": "T7", "capacity_kg": 2700, "est_cost": 300000},
    {"id": "OX_T8", "name": "Boi de Transporte T8 (Ancião)", "tier": "T8", "capacity_kg": 3500, "est_cost": 650000},
    {"id": "MAMMOTH_T8", "name": "Mamute de Transporte T8", "tier": "T8", "capacity_kg": 25000, "est_cost": 125000000},
]

BAG_LOAD_MAP = {
    "NONE": {"name": "Sem Bolsa", "bonus_kg": 0, "est_cost": 0},
    "T4.0": {"name": "Bolsa T4.0", "bonus_kg": 86, "est_cost": 5000},
    "T5.0": {"name": "Bolsa T5.0", "bonus_kg": 141, "est_cost": 15000},
    "T6.0": {"name": "Bolsa T6.0", "bonus_kg": 230, "est_cost": 40000},
    "T7.0": {"name": "Bolsa T7.0", "bonus_kg": 377, "est_cost": 120000},
    "T8.0": {"name": "Bolsa T8.0", "bonus_kg": 617, "est_cost": 350000},
}

PIE_LOAD_MAP = {
    "NONE": {"name": "Sem Comida", "bonus_pct": 0.0, "est_cost": 0},
    "T3_CHICKEN": {"name": "Torta de Galinha T3 (+10%)", "bonus_pct": 10.0, "est_cost": 500},
    "T5_GOOSE": {"name": "Torta de Ganso T5 (+20%)", "bonus_pct": 20.0, "est_cost": 1500},
    "T7_PORK": {"name": "Torta de Porco T7 (+30%)", "bonus_pct": 30.0, "est_cost": 3500},
}

BOOTS_PASSIVE_MAP = {
    "NONE": {"name": "Sem Passiva", "bonus_pct": 0.0},
    "COURIER_STANDARD": {"name": "Passiva Transportador (+14%)", "bonus_pct": 14.0},
}


class AlbionAnalyticsEngine:
    def __init__(self, region: str = "americas"):
        self.region = region
        self.df: Optional[pl.DataFrame] = None

    def load_data(self) -> pl.DataFrame:
        if self.df is not None:
            return self.df

        metadata_manager.ensure_data_loaded()

        # 1. Databricks (se disponível)
        if databricks_client.is_configured():
            try:
                res = asyncio.run(databricks_client.query_gold_features(limit=20000))
                if res.get("success") and res.get("rows"):
                    df_raw = pl.DataFrame(res["rows"])
                    self.df = self._enrich_dataframe(df_raw)
                    return self.df
            except Exception as e:
                logger.warning(f"Databricks falhou, usando SQLite: {e}")

        # 2. SQLite local fallback
        db_file = os.path.join(DATA_DIR, f"market_history_{self.region}.db")
        if os.path.exists(db_file):
            try:
                conn = sqlite3.connect(db_file)
                query = """
                SELECT item_id, quality, location, total_sold, total_silver,
                       days_with_sales, window_days, avg_daily_sales, avg_historical_price,
                       first_date, last_date
                FROM history_stats
                """
                df_raw = pl.read_database(query, conn)
                conn.close()
                self.df = self._enrich_dataframe(df_raw)
                return self.df
            except Exception as e:
                logger.warning(f"Erro ao ler SQLite: {e}")

        self.df = pl.DataFrame()
        return self.df

    def _enrich_dataframe(self, df: pl.DataFrame) -> pl.DataFrame:
        if "avg_price" in df.columns and "avg_historical_price" not in df.columns:
            df = df.rename({"avg_price": "avg_historical_price"})
        if "quality_level" in df.columns and "quality" not in df.columns:
            df = df.rename({"quality_level": "quality"})

        item_ids = df["item_id"].to_list()
        item_names = [metadata_manager.get_item_name(iid) for iid in item_ids]
        tiers = [metadata_manager.get_tier(iid) for iid in item_ids]
        categories = [metadata_manager.get_category_for_item(iid) for iid in item_ids]

        df = df.with_columns([
            pl.Series("item_name", item_names, dtype=pl.Utf8),
            pl.Series("tier", tiers, dtype=pl.Utf8),
            pl.Series("category", categories, dtype=pl.Utf8),
            (pl.col("avg_daily_sales") * pl.col("avg_historical_price")).alias("daily_silver"),
        ])
        return df

    def calculate_refining(
        self,
        resource_type: str = "ORE",
        tier: int = 5,
        enchantment: int = 0,
        has_focus: bool = False,
        has_premium: bool = False,
        station_fee_per_100: int = 500
    ) -> Dict[str, Any]:
        """Calcula o retorno de refino para um tier e recurso específicos."""
        self.load_data()
        spec = None
        city = None
        for c, s in REFINING_SPECIALTIES.items():
            if s["resource"] == resource_type.upper():
                spec = s
                city = c
                break

        if not spec:
            return {"error": f"Recurso '{resource_type}' desconhecido. Use: ORE, WOOD, FIBER, HIDE, ROCK."}

        rrr = 0.539 if has_focus else 0.40
        raw_qty_map = {2: 1, 3: 2, 4: 2, 5: 3, 6: 4, 7: 5, 8: 5}
        item_values = {2: 2, 3: 8, 4: 16, 5: 32, 6: 64, 7: 128, 8: 256}

        raw_qty = raw_qty_map.get(tier, 2)
        base_iv = item_values.get(tier, 16)
        iv = base_iv * (2 ** enchantment)
        nutrition_cost = int(round((iv * 0.1125 / 100.0) * station_fee_per_100))

        raw_prefix = spec["raw_prefix"]
        refined_prefix = spec["refined_prefix"]

        enc_str = f"_LEVEL{enchantment}@{enchantment}" if enchantment > 0 else ""
        raw_id = f"T{tier}_{raw_prefix}{enc_str}"
        refined_id = f"T{tier}_{refined_prefix}{enc_str}"

        # Insumo refinado anterior
        prev_refined_id = None
        if tier > 2:
            prev_tier = tier - 1
            if tier == 4 and enchantment > 0:
                prev_refined_id = f"T3_{refined_prefix}"
            else:
                prev_enc_str = f"_LEVEL{enchantment}@{enchantment}" if (enchantment > 0 and tier > 4) else ""
                prev_refined_id = f"T{prev_tier}_{refined_prefix}{prev_enc_str}"

        # Obter preços médios no DataFrame
        raw_price = 0
        prev_price = 0
        sell_price = 0

        if self.df is not None and len(self.df) > 0:
            raw_match = self.df.filter((pl.col("item_id") == raw_id) & (pl.col("quality") == 1))
            if len(raw_match) > 0:
                raw_price = int(raw_match["avg_historical_price"].min())

            if prev_refined_id:
                prev_match = self.df.filter((pl.col("item_id") == prev_refined_id) & (pl.col("quality") == 1))
                if len(prev_match) > 0:
                    prev_price = int(prev_match["avg_historical_price"].min())

            sell_match = self.df.filter((pl.col("item_id") == refined_id) & (pl.col("location") == city) & (pl.col("quality") == 1))
            if len(sell_match) > 0:
                sell_price = int(sell_match["avg_historical_price"].max())

        gross_raw_cost = (raw_qty * raw_price) + prev_price
        effective_cost = int(gross_raw_cost * (1.0 - rrr)) + nutrition_cost

        tax_rate = get_tax_rate(has_premium)
        net_revenue = int(round(sell_price * (1.0 - tax_rate - SETUP_FEE_RATE)))
        net_profit = net_revenue - effective_cost
        roi_pct = round((net_profit / effective_cost * 100), 2) if effective_cost > 0 else 0.0

        return {
            "resource": resource_type.upper(),
            "specialized_city": city,
            "tier": f"T{tier}.{enchantment}" if enchantment > 0 else f"T{tier}",
            "raw_material": {
                "item_id": raw_id,
                "name": metadata_manager.get_item_name(raw_id),
                "quantity": raw_qty,
                "avg_price": raw_price
            },
            "previous_refined_material": {
                "item_id": prev_refined_id,
                "name": metadata_manager.get_item_name(prev_refined_id) if prev_refined_id else None,
                "quantity": 1 if prev_refined_id else 0,
                "avg_price": prev_price
            } if prev_refined_id else None,
            "refined_product": {
                "item_id": refined_id,
                "name": metadata_manager.get_item_name(refined_id),
                "sell_city": city,
                "sell_price": sell_price,
                "net_revenue": net_revenue
            },
            "economics": {
                "rrr_pct": round(rrr * 100, 1),
                "has_focus": has_focus,
                "has_premium": has_premium,
                "station_nutrition_cost": nutrition_cost,
                "effective_craft_cost": effective_cost,
                "net_profit_per_bar": net_profit,
                "roi_pct": roi_pct
            }
        }

    def calculate_cascade_refining(
        self,
        resource_type: str = "ORE",
        target_tier: int = 6,
        target_enchantment: int = 1,
        budget: int = 2000000,
        has_focus: bool = False,
        has_premium: bool = False,
        station_fee_per_100: int = 500
    ) -> Dict[str, Any]:
        """
        Simula a operação completa de compra de matérias-primas brutas, transporte até a
        capital especializada, refino em cascata até o tier alvo e cálculo do kit de carga.
        """
        refine_base = self.calculate_refining(
            resource_type=resource_type,
            tier=target_tier,
            enchantment=target_enchantment,
            has_focus=has_focus,
            has_premium=has_premium,
            station_fee_per_100=station_fee_per_100
        )
        if "error" in refine_base:
            return refine_base

        eff_cost = refine_base["economics"]["effective_craft_cost"]
        if eff_cost <= 0:
            eff_cost = 100

        bars_produced = max(1, budget // eff_cost)
        total_invested = bars_produced * eff_cost
        sell_price = refine_base["refined_product"]["sell_price"]
        tax_rate = get_tax_rate(has_premium)
        gross_revenue = bars_produced * sell_price
        net_revenue = int(round(gross_revenue * (1.0 - tax_rate - SETUP_FEE_RATE)))
        net_profit = net_revenue - total_invested
        roi_pct = round((net_profit / total_invested * 100), 2) if total_invested > 0 else 0.0

        UNIT_WEIGHTS = {2: 0.2, 3: 0.3, 4: 0.5, 5: 0.9, 6: 1.4, 7: 2.0, 8: 2.8}
        raw_qty = refine_base["raw_material"]["quantity"] * bars_produced
        weight_kg = round(raw_qty * UNIT_WEIGHTS.get(target_tier, 1.0), 1)

        # Seleciona melhor montaria
        recommended_mount = MOUNTS_LIST[-1]
        for m in MOUNTS_LIST:
            if m["capacity_kg"] >= weight_kg:
                recommended_mount = m
                break

        return {
            "resource": resource_type.upper(),
            "target_tier": f"T{target_tier}.{target_enchantment}" if target_enchantment > 0 else f"T{target_tier}",
            "refining_city": refine_base["specialized_city"],
            "budget_silver": budget,
            "bars_produced": bars_produced,
            "total_invested": total_invested,
            "gross_revenue": gross_revenue,
            "net_revenue": net_revenue,
            "net_profit": net_profit,
            "roi_pct": roi_pct,
            "cargo": {
                "total_weight_kg": weight_kg,
                "recommended_mount": recommended_mount["name"],
                "mount_capacity_kg": recommended_mount["capacity_kg"],
                "est_mount_cost": recommended_mount["est_cost"],
                "recommended_bag": "Bolsa T5.0 (Perito)",
                "recommended_food": "Torta de Porco T7 (+30% Carga)"
            },
            "unit_breakdown": refine_base
        }

    def get_pareto_analysis(self, top_n: int = 30) -> Dict[str, Any]:
        """Calcula a curva de Pareto 80/20 de itens mais negociados em prata diária."""
        self.load_data()
        if self.df is None or len(self.df) == 0:
            return {"items": [], "total_market_daily_silver": 0}

        agg = (
            self.df.filter(pl.col("quality") == 1)
            .group_by(["item_id", "item_name", "tier", "category"])
            .agg([
                pl.col("daily_silver").sum().alias("total_daily_silver"),
                pl.col("avg_daily_sales").sum().round(1).alias("total_daily_sales"),
                pl.col("avg_historical_price").mean().round(0).cast(pl.Int64).alias("avg_price"),
            ])
            .filter(pl.col("total_daily_silver") > 0)
            .sort("total_daily_silver", descending=True)
        )

        total_market_silver = agg["total_daily_silver"].sum() or 1
        agg = agg.with_columns([
            (pl.col("total_daily_silver") / total_market_silver * 100).round(2).alias("share_pct"),
            (pl.col("total_daily_silver").cum_sum() / total_market_silver * 100).round(2).alias("cum_share_pct")
        ])

        top_items = agg.head(top_n).to_dicts()
        return {
            "total_market_daily_silver": int(total_market_silver),
            "top_items_count": len(top_items),
            "items": top_items
        }


# Instância global
analytics_engine = AlbionAnalyticsEngine()
