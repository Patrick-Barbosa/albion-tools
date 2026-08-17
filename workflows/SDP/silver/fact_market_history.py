# =============================================================================
# SILVER FACT: Market History
# =============================================================================
# Parse completo do raw_json do Bronze para histórico de transações
# =============================================================================

from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, LongType, IntegerType, ArrayType


@dp.table(
    name="fact_market_history",
    comment="Fato de histórico de transações do mercado",
    cluster_by=["ingestion_date", "location", "item_id"]
)
def fact_market_history():
    """
    Lê streaming do Bronze e faz parse completo do raw_json.
    Market history contém arrays de timestamps, item_count, avg_price.
    """
    # Schema do JSON (simplificado - arrays serão exploded)
    json_schema = StructType([
        StructField("item_id", StringType(), True),
        StructField("location", StringType(), True),
        StructField("quality", IntegerType(), True),
        StructField("timescale", IntegerType(), True),
        StructField("data", ArrayType(
            StructType([
                StructField("timestamp", StringType(), True),
                StructField("item_count", LongType(), True),
                StructField("avg_price", LongType(), True)
            ])
        ), True)
    ])
    
    df = (
        spark.readStream
        .table("main.bronze.market_history_raw")
        .withColumn("parsed_json", F.from_json(F.col("raw_json"), json_schema))
    )
    
    # Flatten + Explode array de transações
    return (
        df
        .select(
            # Metadata de ingressão
            F.col("ingestion_timestamp"),
            F.col("ingestion_date"),
            F.col("source_topic"),
            
            # Campos do JSON
            F.col("parsed_json.item_id").alias("item_id"),
            F.col("parsed_json.location").alias("location"),
            F.col("parsed_json.quality").alias("quality"),
            F.col("parsed_json.timescale").alias("timescale"),
            
            # Explode array de dados
            F.explode(F.col("parsed_json.data")).alias("data_point")
        )
        .select(
            "ingestion_timestamp",
            "ingestion_date",
            "source_topic",
            "item_id",
            "location",
            "quality",
            "timescale",
            F.to_timestamp(F.col("data_point.timestamp")).alias("transaction_timestamp"),
            F.col("data_point.item_count").alias("item_count"),
            F.col("data_point.avg_price").alias("avg_price")
        )
        .withColumn("processed_at", F.current_timestamp())
    )