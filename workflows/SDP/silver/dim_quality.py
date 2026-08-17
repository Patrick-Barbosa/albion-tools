# =============================================================================
# SILVER DIMENSION: Quality Levels (Static Reference Data)
# =============================================================================
# Dimensão estática com os níveis de qualidade do Albion Online
# 1 = Normal, 2 = Good, 3 = Outstanding, 4 = Excellent, 5 = Masterpiece
# =============================================================================

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.materialized_view(
    name="dim_quality",
    comment="Dimensão de qualidade de itens do Albion Online",
    cluster_by=["quality_id"]
)
def dim_quality():
    """
    Cria dimensão estática de qualidade.
    Não lê de fonte externa - cria os dados hardcoded.
    """
    quality_data = [
        (1, "Normal", 0.0),
        (2, "Good", 10.0),
        (3, "Outstanding", 20.0),
        (4, "Excellent", 30.0),
        (5, "Masterpiece", 40.0)
    ]
    
    return spark.createDataFrame(
        quality_data,
        ["quality_id", "quality_name", "quality_bonus_pct"]
    ).withColumn("created_at", F.current_timestamp())