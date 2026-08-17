# =============================================================================
# SILVER FACT: Market Orders
# =============================================================================
# Parse completo do raw_json do Bronze para estrutura normalizada
# Calcula spread, ROI e métricas derivadas
# =============================================================================

from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, LongType, IntegerType


@dp.table(
    name="fact_market_orders",
    comment="Fato de market orders com parse completo do JSON e métricas calculadas",
    cluster_by=["ingestion_date", "city", "item_id"]
)
def fact_market_orders():
    """
    Lê streaming do Bronze e faz parse completo do raw_json.
    Calcula spread (sell_price_min - buy_price_max) e ROI.
    """
    # Schema do JSON original
    json_schema = StructType([
        StructField("item_id", StringType(), True),
        StructField("city", StringType(), True),
        StructField("quality", IntegerType(), True),
        StructField("sell_price_min", LongType(), True),
        StructField("sell_price_min_date", StringType(), True),
        StructField("sell_price_max", LongType(), True),
        StructField("sell_price_max_date", StringType(), True),
        StructField("buy_price_min", LongType(), True),
        StructField("buy_price_min_date", StringType(), True),
        StructField("buy_price_max", LongType(), True),
        StructField("buy_price_max_date", StringType(), True)
    ])
    
    df = (
        spark.readStream
        .table("main.bronze.market_orders_raw")
        .withColumn("parsed_json", F.from_json(F.col("raw_json"), json_schema))
    )
    
    # Flatten + Calculate metrics
    return (
        df
        .select(
            # Metadata de ingressão
            F.col("ingestion_timestamp"),
            F.col("ingestion_date"),
            F.col("source_topic"),
            
            # Campos do JSON
            F.col("parsed_json.item_id").alias("item_id"),
            F.col("parsed_json.city").alias("city"),
            F.col("parsed_json.quality").alias("quality"),
            
            # Preços de venda
            F.col("parsed_json.sell_price_min").alias("sell_price_min"),
            F.to_timestamp(F.col("parsed_json.sell_price_min_date")).alias("sell_price_min_date"),
            F.col("parsed_json.sell_price_max").alias("sell_price_max"),
            F.to_timestamp(F.col("parsed_json.sell_price_max_date")).alias("sell_price_max_date"),
            
            # Preços de compra
            F.col("parsed_json.buy_price_min").alias("buy_price_min"),
            F.to_timestamp(F.col("parsed_json.buy_price_min_date")).alias("buy_price_min_date"),
            F.col("parsed_json.buy_price_max").alias("buy_price_max"),
            F.to_timestamp(F.col("parsed_json.buy_price_max_date")).alias("buy_price_max_date")
        )
        .withColumn(
            "spread",
            F.when(
                (F.col("sell_price_min").isNotNull()) & (F.col("buy_price_max").isNotNull()),
                F.col("sell_price_min") - F.col("buy_price_max")
            ).otherwise(None)
        )
        .withColumn(
            "spread_pct",
            F.when(
                (F.col("buy_price_max").isNotNull()) & (F.col("buy_price_max") > 0),
                (F.col("spread") / F.col("buy_price_max") * 100)
            ).otherwise(None)
        )
        .withColumn(
            "roi_pct",
            F.when(
                (F.col("buy_price_max").isNotNull()) & (F.col("buy_price_max") > 0),
                ((F.col("sell_price_min") * 0.935) - F.col("buy_price_max")) / F.col("buy_price_max") * 100
            ).otherwise(None)
        )
        .withColumn("is_profitable", F.col("roi_pct") > 5.0)
        .withColumn("processed_at", F.current_timestamp())
    )