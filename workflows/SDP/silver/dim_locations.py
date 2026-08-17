# =============================================================================
# SILVER DIMENSION: Locations
# =============================================================================
# Extrai localizações únicas do Bronze (city e location)
# =============================================================================

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="dim_locations",
    comment="Dimensão de localizações do Albion Online",
    cluster_by=["location_type", "region"]
)
def dim_locations():
    """
    Extrai localizações únicas das tabelas Bronze.
    Classifica cidades em Royal (capitais) vs Outlands.
    """
    # Cidades do market_orders
    cities = (
        spark.read.table("main.bronze.market_orders_raw")
        .select(F.col("city").alias("location_id"))
        .distinct()
    )
    
    # Locations do market_history
    locations = (
        spark.read.table("main.bronze.market_history_raw")
        .select(F.col("location").alias("location_id"))
        .distinct()
    )
    
    # UNION de todas as localizações
    all_locations = cities.union(locations).distinct()
    
    # Classificação por tipo e região
    return (
        all_locations
        # REMOVIDO: Filtros de NULL/UNKNOWN/PARSE_ERROR para puxar TODOS os dados
        .withColumn("location_name", F.col("location_id"))
        .withColumn(
            "location_type",
            F.when(F.col("location_id") == "Black Market", "BlackMarket")
            .otherwise("City")
        )
        .withColumn(
            "region",
            F.when(
                F.col("location_id").isin(
                    "Caerleon", "Bridgewatch", "Fort Sterling", 
                    "Lymhurst", "Martlock", "Thetford"
                ),
                "Royal"
            )
            .otherwise("Outlands")
        )
        .withColumn("is_market_enabled", F.lit(True))
        .withColumn("created_at", F.current_timestamp())
        .withColumn("updated_at", F.current_timestamp())
        .select(
            "location_id",
            "location_name",
            "location_type",
            "region",
            "is_market_enabled",
            "created_at",
            "updated_at"
        )
    )