# =============================================================================
# GOLD ANALYSIS: Cross-City Flipping Opportunities
# =============================================================================
# Identifica oportunidades de arbitragem entre cidades
# Compra em cidade A (buy_price_max) e vende em cidade B (sell_price_min)
# =============================================================================

from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.window import Window


@dp.materialized_view(
    name="flipping_opportunities",
    comment="Análise de oportunidades de cross-city arbitrage com cálculo de lucro líquido",
    cluster_by=["net_profit", "item_id"]
)
def flipping_opportunities():
    """
    Identifica oportunidades de flipping cross-city.
    
    Lógica:
    - Busca pares de cidades (buy_city != sell_city)
    - Calcula gross_profit = sell_price_min - buy_price_max
    - Aplica taxa de mercado (6.5%)
    - Calcula ROI líquido
    - Filtra apenas oportunidades lucrativas (net_profit > 0)
    - Ordena por net_profit DESC
    """
    # Lê dados frescos do fato (batch)
    orders = spark.read.table("workspace.default.fact_market_orders")
    
    # Self-join para comparar preços entre cidades
    buy_city = orders.alias("buy")
    sell_city = orders.alias("sell")
    
    flips = (
        buy_city.join(
            sell_city,
            (
                (F.col("buy.item_id") == F.col("sell.item_id")) &
                (F.col("buy.quality") == F.col("sell.quality")) &
                (F.col("buy.city") != F.col("sell.city")) &
                (F.col("buy.buy_price_max").isNotNull()) &
                (F.col("sell.sell_price_min").isNotNull())
            ),
            "inner"
        )
        .select(
            F.col("buy.item_id").alias("item_id"),
            F.col("buy.quality").alias("quality"),
            F.col("buy.city").alias("buy_city"),
            F.col("buy.buy_price_max").alias("buy_price"),
            F.col("buy.buy_price_max_date").alias("buy_price_date"),
            F.col("sell.city").alias("sell_city"),
            F.col("sell.sell_price_min").alias("sell_price"),
            F.col("sell.sell_price_min_date").alias("sell_price_date"),
            F.greatest(
                F.col("buy.ingestion_timestamp"),
                F.col("sell.ingestion_timestamp")
            ).alias("analysis_timestamp")
        )
    )
    
    # Calcula métricas financeiras
    opportunities = (
        flips
        .withColumn(
            "gross_profit",
            F.col("sell_price") - F.col("buy_price")
        )
        .withColumn(
            "market_tax",
            (F.col("sell_price") * 0.065).cast("long")
        )
        .withColumn(
            "net_profit",
            F.col("gross_profit") - F.col("market_tax")
        )
        .withColumn(
            "roi_pct",
            F.when(
                F.col("buy_price") > 0,
                (F.col("net_profit") / F.col("buy_price") * 100)
            ).otherwise(None)
        )
        .withColumn(
            "opportunity_window_minutes",
            (F.unix_timestamp(F.col("sell_price_date")) - 
             F.unix_timestamp(F.col("buy_price_date"))) / 60
        )
        .withColumn(
            "data_freshness_hours",
            (F.unix_timestamp(F.current_timestamp()) - 
             F.unix_timestamp(F.col("analysis_timestamp"))) / 3600
        )
    )
    
    # Filtrar apenas oportunidades válidas
    valid_opportunities = (
        opportunities
        .filter(F.col("net_profit") > 0)  # Lucro positivo
        .filter(F.col("roi_pct") >= 5.0)  # ROI mínimo 5%
        .filter(F.abs(F.col("opportunity_window_minutes")) <= 120)  # Janela de 2h
        .filter(F.col("data_freshness_hours") <= 1)  # Dados com menos de 1h
    )
    
    # Deduplicação: melhor oportunidade por item/quality
    window_spec = Window.partitionBy("item_id", "quality").orderBy(F.desc("net_profit"))
    
    return (
        valid_opportunities
        .withColumn("rank", F.row_number().over(window_spec))
        .filter(F.col("rank") == 1)
        .drop("rank")
        .withColumn("is_active", F.lit(True))
        .withColumn("created_at", F.current_timestamp())
        .select(
            "item_id",
            "quality",
            "buy_city",
            "buy_price",
            "buy_price_date",
            "sell_city",
            "sell_price",
            "sell_price_date",
            "gross_profit",
            "market_tax",
            "net_profit",
            "roi_pct",
            "opportunity_window_minutes",
            "data_freshness_hours",
            "is_active",
            "analysis_timestamp",
            "created_at"
        )
    )