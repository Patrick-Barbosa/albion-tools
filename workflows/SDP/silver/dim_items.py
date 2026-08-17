# =============================================================================
# SILVER DIMENSION: Items
# =============================================================================
# Extrai informações dos item_id do Albion Online
# Formato: T{tier}_{category}[@{enchantment}][_LEVEL{level}]
# Exemplos: T4_LEATHER, T8_2H_ARCANESTAFF@3, T4_POTION_HEAL_LEVEL1
# =============================================================================

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="dim_items",
    comment="Dimensão de itens extraída do item_id do Albion Online",
    cluster_by=["tier", "category"]
)
def dim_items():
    """
    Lê dados únicos do Bronze e extrai metadados do item_id.
    Usa DISTINCT para ter apenas uma linha por item.
    """
    # Ler de ambas as fontes Bronze e fazer UNION
    orders = spark.read.table("main.bronze.market_orders_raw").select("item_id")
    history = spark.read.table("main.bronze.market_history_raw").select("item_id")
    
    items = orders.union(history).distinct()
    
    return (
        items
        # REMOVIDO: Filtros de NULL/UNKNOWN/PARSE_ERROR para puxar TODOS os dados
        .withColumn(
            "tier",
            F.regexp_extract(F.col("item_id"), r"^T(\d+)", 1).cast("int")
        )
        .withColumn(
            "enchantment",
            F.coalesce(
                F.regexp_extract(F.col("item_id"), r"@(\d+)", 1).cast("int"),
                F.lit(0)
            )
        )
        .withColumn(
            "category",
            F.regexp_extract(F.col("item_id"), r"^T\d+_([A-Z0-9_]+)", 1)
        )
        .withColumn(
            "is_artifact",
            F.when(F.col("item_id").contains("ARTIFACT"), True).otherwise(False)
        )
        .withColumn("item_name", F.col("item_id"))  # Placeholder - nome real vem de game data
        .withColumn("created_at", F.current_timestamp())
        .withColumn("updated_at", F.current_timestamp())
        .select(
            "item_id",
            "item_name",
            "tier",
            "enchantment",
            "category",
            "is_artifact",
            "created_at",
            "updated_at"
        )
    )