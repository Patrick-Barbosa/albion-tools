# =============================================================================
# GOLD LAYER: Albion Online - Flipping Opportunities Analysis
# =============================================================================
# Objetivo: Identificar oportunidades de compra/venda entre cidades (flipping)
# Estratégia: Cross-join de todas as cidades para encontrar arbitragem
# 
# Regras de Negócio:
# 1. Cruzar TODAS as cidades (comprar em A, vender em B)
# 2. Filtrar por timestamps na ÚLTIMA HORA (dados frescos)
# 3. Timestamps NÃO vencidos (buy/sell dates válidos)
# 4. Janela de análise: 2 HORAS (oportunidade expira após 2h)
# 5. Flag is_active: TRUE se < 2h E timestamps válidos, FALSE caso contrário
# 6. Particionamento: is_active (sempre consultamos ativos)
# 7. Histórico mantido (inativas ficam registradas)
# =============================================================================

import logging
from datetime import datetime, timedelta
from typing import Optional

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, lit, current_timestamp, 
    when, coalesce,
    md5, concat_ws,
    unix_timestamp, from_unixtime,
    datediff, hour, minute
)
from pyspark.sql.types import StringType, LongType, DoubleType, BooleanType, TimestampType
from delta.tables import DeltaTable

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

class Config:
    """Configurações centralizadas do pipeline Gold"""
    
    # Unity Catalog
    CATALOG = "main"
    SCHEMA_SILVER = "silver"
    SCHEMA_GOLD = "gold"
    
    # Tabelas source (Silver)
    FACT_MARKET_ORDERS = f"{CATALOG}.{SCHEMA_SILVER}.fact_market_orders"
    
    # Tabela target (Gold)
    FLIPPING_OPPORTUNITIES = f"{CATALOG}.{SCHEMA_GOLD}.flipping_opportunities"
    
    # Checkpoint
    CHECKPOINT_TABLE = f"{CATALOG}.{SCHEMA_GOLD}._checkpoints"
    
    # Regras de Negócio
    FRESHNESS_HOURS = 1  # Dados com até 1 hora
    OPPORTUNITY_WINDOW_HOURS = 2  # Oportunidade válida por 2 horas
    MARKET_TAX_PCT = 0.065  # 6.5% taxa em cada transação
    MIN_ROI_PCT = 5.0  # ROI mínimo para considerar lucrativo
    
    # Logging
    LOG_LEVEL = logging.INFO

# =============================================================================
# SETUP LOGGING
# =============================================================================

logging.basicConfig(
    level=Config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CHECKPOINT MANAGEMENT
# =============================================================================

def create_checkpoint_table(spark: SparkSession) -> None:
    """Cria tabela de checkpoints se não existir"""
    ddl = f"""
    CREATE TABLE IF NOT EXISTS {Config.CHECKPOINT_TABLE} (
      pipeline_name STRING,
      last_processed_timestamp TIMESTAMP,
      records_processed BIGINT,
      processing_timestamp TIMESTAMP,
      status STRING
    ) USING DELTA
    COMMENT 'Checkpoints para processamento incremental Gold'
    """
    spark.sql(ddl)
    logger.info(f"✅ Checkpoint table {Config.CHECKPOINT_TABLE} criada/verificada")

def get_checkpoint(spark: SparkSession, pipeline_name: str) -> Optional[datetime]:
    """Retorna o último timestamp processado para um pipeline"""
    try:
        result = spark.sql(f"""
            SELECT MAX(last_processed_timestamp) as last_ts
            FROM {Config.CHECKPOINT_TABLE}
            WHERE pipeline_name = '{pipeline_name}'
            AND status = 'SUCCESS'
        """).collect()
        
        if result and result[0]['last_ts']:
            return result[0]['last_ts']
        return None
    except Exception as e:
        logger.warning(f"Checkpoint não encontrado para {pipeline_name}: {e}")
        return None

def update_checkpoint(
    spark: SparkSession,
    pipeline_name: str,
    last_timestamp: datetime,
    records_count: int,
    status: str = "SUCCESS"
) -> None:
    """Atualiza checkpoint após processamento"""
    checkpoint_data = [(
        pipeline_name,
        last_timestamp,
        records_count,
        datetime.now(),
        status
    )]
    
    df = spark.createDataFrame(
        checkpoint_data,
        ["pipeline_name", "last_processed_timestamp", "records_processed", "processing_timestamp", "status"]
    )
    
    df.write.format("delta").mode("append").saveAsTable(Config.CHECKPOINT_TABLE)
    logger.info(f"✅ Checkpoint atualizado: {pipeline_name} @ {last_timestamp}")

# =============================================================================
# DDL: CRIAÇÃO DA TABELA GOLD
# =============================================================================

def create_gold_table(spark: SparkSession) -> None:
    """Cria tabela Gold de oportunidades de flipping"""
    
    logger.info("Criando schema Gold...")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {Config.CATALOG}.{Config.SCHEMA_GOLD}")
    
    logger.info(f"Criando tabela {Config.FLIPPING_OPPORTUNITIES}...")
    
    ddl = f"""
    CREATE TABLE IF NOT EXISTS {Config.FLIPPING_OPPORTUNITIES} (
      -- Chave única da oportunidade
      opportunity_id STRING,
      
      -- Dimensões
      item_id STRING COMMENT 'Item sendo negociado',
      quality INT COMMENT 'Qualidade do item (1-5)',
      buy_city STRING COMMENT 'Cidade onde comprar',
      sell_city STRING COMMENT 'Cidade onde vender',
      
      -- Preços de referência
      buy_price BIGINT COMMENT 'Preço de compra (buy_price_max)',
      sell_price BIGINT COMMENT 'Preço de venda (sell_price_min)',
      
      -- Métricas de flipping
      gross_profit BIGINT COMMENT 'Lucro bruto (sell - buy)',
      buy_tax BIGINT COMMENT 'Taxa na compra (6.5%)',
      sell_tax BIGINT COMMENT 'Taxa na venda (6.5%)',
      total_tax BIGINT COMMENT 'Taxa total',
      net_profit BIGINT COMMENT 'Lucro líquido após taxas',
      roi_pct DOUBLE COMMENT 'ROI percentual',
      
      -- Timestamps críticos
      buy_timestamp TIMESTAMP COMMENT 'Timestamp do order de compra',
      sell_timestamp TIMESTAMP COMMENT 'Timestamp do order de venda',
      created_at TIMESTAMP COMMENT 'Quando a oportunidade foi identificada',
      updated_at TIMESTAMP COMMENT 'Última atualização',
      expires_at TIMESTAMP COMMENT 'Quando expira (created_at + 2h)',
      
      -- Status da oportunidade
      is_active BOOLEAN COMMENT 'TRUE se ativa, FALSE se expirou',
      inactive_reason STRING COMMENT 'EXPIRED | BUY_ORDER_EXPIRED | SELL_ORDER_EXPIRED',
      
      -- Metadados
      _silver_source_timestamp TIMESTAMP COMMENT 'Timestamp da fonte Silver',
      
      CONSTRAINT pk_opportunities PRIMARY KEY (opportunity_id)
    ) USING DELTA
    CLUSTER BY (is_active, created_at, net_profit)
    TBLPROPERTIES (
      'delta.enableChangeDataFeed' = 'true',
      'delta.autoOptimize.optimizeWrite' = 'true',
      'delta.autoOptimize.autoCompact' = 'true'
    )
    COMMENT 'Oportunidades de flipping entre cidades com status ativo/inativo'
    """
    
    spark.sql(ddl)
    logger.info(f"✅ Tabela {Config.FLIPPING_OPPORTUNITIES} criada/verificada")

# =============================================================================
# ANÁLISE DE OPORTUNIDADES: CROSS-CITY FLIPPING
# =============================================================================

def find_flipping_opportunities(spark: SparkSession) -> DataFrame:
    """
    Identifica oportunidades de flipping entre cidades.
    
    Estratégia:
    1. Lê market_orders da Silver
    2. Filtra dados FRESCOS (última hora)
    3. Filtra timestamps VÁLIDOS (não expirados)
    4. Self-join para cruzar TODAS as cidades (buy_city != sell_city)
    5. Calcula métricas de flipping
    6. Calcula status (ativo/inativo baseado em 2h window)
    """
    
    logger.info("🔍 Buscando oportunidades de flipping entre cidades...")
    
    # Timestamp de referência (agora)
    now_ts = datetime.now()
    freshness_cutoff = now_ts - timedelta(hours=Config.FRESHNESS_HOURS)
    
    logger.info(f"📅 Buscando dados desde: {freshness_cutoff}")
    
    # =========================================================================
    # 1. Ler dados FRESCOS da Silver (última hora)
    # =========================================================================
    
    df_orders = spark.sql(f"""
        SELECT 
            item_id,
            city,
            quality,
            buy_price_max,
            sell_price_min,
            buy_price_max_date,
            sell_price_min_date,
            market_timestamp,
            ingestion_timestamp,
            processing_timestamp
        FROM {Config.FACT_MARKET_ORDERS}
        WHERE 
            -- Dados frescos (última hora)
            processing_timestamp >= '{freshness_cutoff}'
            
            -- Preços válidos (> 0)
            AND buy_price_max > 0
            AND sell_price_min > 0
            
            -- Timestamps não nulos
            AND buy_price_max_date IS NOT NULL
            AND sell_price_min_date IS NOT NULL
            
            -- Timestamps NÃO vencidos (dentro da última hora)
            AND buy_price_max_date >= '{freshness_cutoff}'
            AND sell_price_min_date >= '{freshness_cutoff}'
    """)
    
    count_fresh = df_orders.count()
    logger.info(f"📊 {count_fresh} orders frescos e válidos encontrados")
    
    if count_fresh == 0:
        logger.warning("⚠️  Nenhum order fresco encontrado. Retornando DataFrame vazio.")
        return spark.createDataFrame([], schema="opportunity_id STRING")
    
    # =========================================================================
    # 2. Self-join para cruzar TODAS as cidades (A → B)
    # =========================================================================
    
    logger.info("🔄 Cruzando todas as cidades (buy_city x sell_city)...")
    
    # Renomear para evitar conflitos
    df_buy = df_orders.alias("buy").select(
        col("item_id").alias("buy_item_id"),
        col("city").alias("buy_city"),
        col("quality").alias("buy_quality"),
        col("buy_price_max").alias("buy_price"),
        col("buy_price_max_date").alias("buy_timestamp"),
        col("processing_timestamp").alias("buy_processing_ts")
    )
    
    df_sell = df_orders.alias("sell").select(
        col("item_id").alias("sell_item_id"),
        col("city").alias("sell_city"),
        col("quality").alias("sell_quality"),
        col("sell_price_min").alias("sell_price"),
        col("sell_price_min_date").alias("sell_timestamp"),
        col("processing_timestamp").alias("sell_processing_ts")
    )
    
    # Cross-join nas condições:
    # - Mesmo item_id
    # - Mesma quality
    # - Cidades DIFERENTES
    df_opportunities = df_buy.join(
        df_sell,
        (df_buy["buy_item_id"] == df_sell["sell_item_id"]) &
        (df_buy["buy_quality"] == df_sell["sell_quality"]) &
        (df_buy["buy_city"] != df_sell["sell_city"]),
        "inner"
    )
    
    count_cross = df_opportunities.count()
    logger.info(f"🔗 {count_cross} combinações cidade-a-cidade encontradas")
    
    if count_cross == 0:
        logger.warning("⚠️  Nenhuma oportunidade cross-city encontrada")
        return spark.createDataFrame([], schema="opportunity_id STRING")
    
    # =========================================================================
    # 3. Calcular métricas de flipping
    # =========================================================================
    
    logger.info("💰 Calculando métricas de flipping...")
    
    df_with_metrics = df_opportunities \
        .withColumn("gross_profit", col("sell_price") - col("buy_price")) \
        .withColumn("buy_tax", (col("buy_price") * lit(Config.MARKET_TAX_PCT)).cast("bigint")) \
        .withColumn("sell_tax", (col("sell_price") * lit(Config.MARKET_TAX_PCT)).cast("bigint")) \
        .withColumn("total_tax", col("buy_tax") + col("sell_tax")) \
        .withColumn("net_profit", col("gross_profit") - col("total_tax")) \
        .withColumn(
            "roi_pct",
            when(
                col("buy_price") > 0,
                (col("net_profit") / col("buy_price")) * 100
            ).otherwise(0.0)
        )
    
    # Filtrar apenas oportunidades lucrativas
    df_profitable = df_with_metrics.filter(
        (col("net_profit") > 0) & (col("roi_pct") >= lit(Config.MIN_ROI_PCT))
    )
    
    count_profitable = df_profitable.count()
    logger.info(f"✅ {count_profitable} oportunidades LUCRATIVAS (ROI >= {Config.MIN_ROI_PCT}%)")
    
    if count_profitable == 0:
        logger.warning("⚠️  Nenhuma oportunidade lucrativa encontrada")
        return spark.createDataFrame([], schema="opportunity_id STRING")
    
    # =========================================================================
    # 4. Adicionar timestamps e status
    # =========================================================================
    
    logger.info("⏰ Adicionando timestamps e calculando status...")
    
    df_final = df_profitable \
        .withColumn("created_at", current_timestamp()) \
        .withColumn("updated_at", current_timestamp()) \
        .withColumn(
            "expires_at",
            from_unixtime(
                unix_timestamp(col("created_at")) + (Config.OPPORTUNITY_WINDOW_HOURS * 3600)
            )
        ) \
        .withColumn(
            "is_active",
            when(
                # Ativa se:
                # 1. Ainda não expirou (< 2h desde criação)
                (unix_timestamp(current_timestamp()) < unix_timestamp(col("expires_at"))) &
                # 2. Timestamps de buy/sell ainda frescos (< 1h)
                (unix_timestamp(current_timestamp()) - unix_timestamp(col("buy_timestamp")) < Config.FRESHNESS_HOURS * 3600) &
                (unix_timestamp(current_timestamp()) - unix_timestamp(col("sell_timestamp")) < Config.FRESHNESS_HOURS * 3600),
                lit(True)
            ).otherwise(lit(False))
        ) \
        .withColumn(
            "inactive_reason",
            when(
                col("is_active") == lit(True),
                lit(None).cast(StringType())
            ).when(
                unix_timestamp(current_timestamp()) >= unix_timestamp(col("expires_at")),
                lit("EXPIRED")
            ).when(
                unix_timestamp(current_timestamp()) - unix_timestamp(col("buy_timestamp")) >= Config.FRESHNESS_HOURS * 3600,
                lit("BUY_ORDER_EXPIRED")
            ).when(
                unix_timestamp(current_timestamp()) - unix_timestamp(col("sell_timestamp")) >= Config.FRESHNESS_HOURS * 3600,
                lit("SELL_ORDER_EXPIRED")
            ).otherwise(lit("UNKNOWN"))
        ) \
        .withColumn(
            "opportunity_id",
            md5(concat_ws("|", col("buy_item_id"), col("buy_quality"), col("buy_city"), col("sell_city"), col("created_at")))
        ) \
        .withColumn(
            "_silver_source_timestamp",
            when(
                col("buy_processing_ts") > col("sell_processing_ts"),
                col("buy_processing_ts")
            ).otherwise(col("sell_processing_ts"))
        )
    
    # Selecionar colunas finais
    df_result = df_final.select(
        col("opportunity_id"),
        col("buy_item_id").alias("item_id"),
        col("buy_quality").alias("quality"),
        col("buy_city"),
        col("sell_city"),
        col("buy_price"),
        col("sell_price"),
        col("gross_profit"),
        col("buy_tax"),
        col("sell_tax"),
        col("total_tax"),
        col("net_profit"),
        col("roi_pct"),
        col("buy_timestamp"),
        col("sell_timestamp"),
        col("created_at"),
        col("updated_at"),
        col("expires_at"),
        col("is_active"),
        col("inactive_reason"),
        col("_silver_source_timestamp")
    )
    
    return df_result

# =============================================================================
# UPDATE EXISTING OPPORTUNITIES STATUS
# =============================================================================

def update_opportunities_status(spark: SparkSession) -> None:
    """
    Atualiza status de oportunidades EXISTENTES na Gold.
    
    Marca como inativas:
    - Oportunidades que expiraram (> 2h)
    - Oportunidades cujos timestamps de buy/sell venceram
    """
    
    logger.info("🔄 Atualizando status de oportunidades existentes...")
    
    try:
        # Verificar se tabela existe
        spark.sql(f"DESCRIBE TABLE {Config.FLIPPING_OPPORTUNITIES}")
        
        # Atualizar oportunidades que ficaram inativas
        update_sql = f"""
        UPDATE {Config.FLIPPING_OPPORTUNITIES}
        SET 
            is_active = FALSE,
            inactive_reason = CASE
                WHEN UNIX_TIMESTAMP(CURRENT_TIMESTAMP()) >= UNIX_TIMESTAMP(expires_at) THEN 'EXPIRED'
                WHEN UNIX_TIMESTAMP(CURRENT_TIMESTAMP()) - UNIX_TIMESTAMP(buy_timestamp) >= {Config.FRESHNESS_HOURS * 3600} THEN 'BUY_ORDER_EXPIRED'
                WHEN UNIX_TIMESTAMP(CURRENT_TIMESTAMP()) - UNIX_TIMESTAMP(sell_timestamp) >= {Config.FRESHNESS_HOURS * 3600} THEN 'SELL_ORDER_EXPIRED'
                ELSE 'UNKNOWN'
            END,
            updated_at = CURRENT_TIMESTAMP()
        WHERE 
            is_active = TRUE
            AND (
                -- Expirou (> 2h)
                UNIX_TIMESTAMP(CURRENT_TIMESTAMP()) >= UNIX_TIMESTAMP(expires_at)
                OR
                -- Timestamps vencidos (> 1h)
                UNIX_TIMESTAMP(CURRENT_TIMESTAMP()) - UNIX_TIMESTAMP(buy_timestamp) >= {Config.FRESHNESS_HOURS * 3600}
                OR
                UNIX_TIMESTAMP(CURRENT_TIMESTAMP()) - UNIX_TIMESTAMP(sell_timestamp) >= {Config.FRESHNESS_HOURS * 3600}
            )
        """
        
        spark.sql(update_sql)
        logger.info("✅ Status de oportunidades existentes atualizado")
        
    except Exception as e:
        logger.info(f"ℹ️  Tabela ainda não existe ou erro ao atualizar: {e}")

# =============================================================================
# MERGE INCREMENTAL
# =============================================================================

def merge_opportunities(spark: SparkSession, df_new: DataFrame) -> None:
    """
    Faz MERGE de novas oportunidades na tabela Gold.
    
    MERGE strategy:
    - MATCHED: Atualiza se status mudou
    - NOT MATCHED: Insere nova oportunidade
    """
    
    if df_new.count() == 0:
        logger.info("✅ Nenhuma oportunidade nova para fazer MERGE")
        return
    
    logger.info(f"💾 Fazendo MERGE de oportunidades em {Config.FLIPPING_OPPORTUNITIES}...")
    
    try:
        delta_table = DeltaTable.forName(spark, Config.FLIPPING_OPPORTUNITIES)
        
        delta_table.alias("target").merge(
            df_new.alias("source"),
            "target.opportunity_id = source.opportunity_id"
        ).whenMatchedUpdate(
            set={
                "updated_at": col("source.updated_at"),
                "is_active": col("source.is_active"),
                "inactive_reason": col("source.inactive_reason")
            }
        ).whenNotMatchedInsertAll().execute()
        
        logger.info("✅ MERGE concluído com sucesso")
        
    except Exception as e:
        logger.error(f"❌ Erro ao fazer MERGE: {e}")
        raise

# =============================================================================
# PROCESSAMENTO PRINCIPAL
# =============================================================================

def process_flipping_opportunities(spark: SparkSession) -> None:
    """
    Processamento principal: Silver → Gold
    
    Pipeline:
    1. Atualizar status de oportunidades existentes
    2. Buscar novas oportunidades
    3. MERGE na Gold
    4. Atualizar checkpoint
    """
    
    pipeline_name = "flipping_opportunities_silver_to_gold"
    logger.info(f"🚀 Iniciando processamento: {pipeline_name}")
    
    # 1. Atualizar status de oportunidades existentes
    update_opportunities_status(spark)
    
    # 2. Buscar novas oportunidades
    df_opportunities = find_flipping_opportunities(spark)
    
    if df_opportunities.count() == 0:
        logger.info("✅ Nenhuma oportunidade nova encontrada")
        return
    
    # 3. MERGE
    merge_opportunities(spark, df_opportunities)
    
    # 4. Atualizar checkpoint
    max_timestamp = datetime.now()
    count = df_opportunities.count()
    update_checkpoint(spark, pipeline_name, max_timestamp, count)
    
    logger.info(f"✅ Processamento concluído: {count} oportunidades processadas")

# =============================================================================
# CONSULTAS ÚTEIS PARA ANÁLISE
# =============================================================================

def print_analysis_queries():
    """
    Imprime queries SQL úteis para análise das oportunidades.
    """
    
    queries = f"""
    ╔════════════════════════════════════════════════════════════════════════════╗
    ║           QUERIES DE ANÁLISE - FLIPPING OPPORTUNITIES                     ║
    ╚════════════════════════════════════════════════════════════════════════════╝
    
    -- 1️⃣  TOP 10 OPORTUNIDADES ATIVAS (Maior ROI)
    SELECT 
        item_id, quality,
        buy_city, sell_city,
        buy_price, sell_price,
        net_profit, roi_pct,
        expires_at
    FROM {Config.FLIPPING_OPPORTUNITIES}
    WHERE is_active = TRUE
    ORDER BY roi_pct DESC
    LIMIT 10;
    
    -- 2️⃣  OPORTUNIDADES POR CIDADE (Onde comprar)
    SELECT 
        buy_city,
        COUNT(*) as total_opportunities,
        AVG(net_profit) as avg_profit,
        AVG(roi_pct) as avg_roi
    FROM {Config.FLIPPING_OPPORTUNITIES}
    WHERE is_active = TRUE
    GROUP BY buy_city
    ORDER BY avg_profit DESC;
    
    -- 3️⃣  OPORTUNIDADES POR ROTA (A → B)
    SELECT 
        buy_city || ' → ' || sell_city as route,
        COUNT(*) as opportunities,
        AVG(net_profit) as avg_profit,
        MAX(net_profit) as max_profit
    FROM {Config.FLIPPING_OPPORTUNITIES}
    WHERE is_active = TRUE
    GROUP BY buy_city, sell_city
    ORDER BY avg_profit DESC
    LIMIT 20;
    
    -- 4️⃣  HISTÓRICO: Oportunidades que expiraram
    SELECT 
        inactive_reason,
        COUNT(*) as total
    FROM {Config.FLIPPING_OPPORTUNITIES}
    WHERE is_active = FALSE
    GROUP BY inactive_reason;
    
    -- 5️⃣  ITENS MAIS LUCRATIVOS (Ativos)
    SELECT 
        item_id,
        COUNT(*) as opportunities,
        AVG(net_profit) as avg_profit,
        MAX(net_profit) as best_profit
    FROM {Config.FLIPPING_OPPORTUNITIES}
    WHERE is_active = TRUE
    GROUP BY item_id
    ORDER BY avg_profit DESC
    LIMIT 10;
    
    -- 6️⃣  DASHBOARD: Resumo Geral
    SELECT 
        COUNT(*) as total_opportunities,
        SUM(CASE WHEN is_active = TRUE THEN 1 ELSE 0 END) as active,
        SUM(CASE WHEN is_active = FALSE THEN 1 ELSE 0 END) as inactive,
        AVG(CASE WHEN is_active = TRUE THEN net_profit END) as avg_profit_active,
        MAX(CASE WHEN is_active = TRUE THEN roi_pct END) as max_roi_active
    FROM {Config.FLIPPING_OPPORTUNITIES};
    """
    
    print(queries)

# =============================================================================
# MAIN: PONTO DE ENTRADA
# =============================================================================

def main():
    """Ponto de entrada do pipeline Gold"""
    
    logger.info("="*80)
    logger.info("GOLD LAYER: Albion Online - Flipping Opportunities Analysis")
    logger.info("Estratégia: Cross-City Arbitrage + Status Tracking (Ativo/Inativo)")
    logger.info("="*80)
    
    # Criar SparkSession
    spark = SparkSession.builder \
        .appName("Gold-Albion-Flipping-Analysis") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .getOrCreate()
    
    logger.info(f"✅ Spark Session criada: {spark.version}")
    
    # 1. Criar estrutura Gold
    logger.info("\n📐 FASE 1: Criando estrutura Gold...")
    create_checkpoint_table(spark)
    create_gold_table(spark)
    
    # 2. Processar oportunidades
    logger.info("\n💎 FASE 2: Processando oportunidades de flipping...")
    try:
        process_flipping_opportunities(spark)
    except Exception as e:
        logger.error(f"❌ Erro ao processar oportunidades: {e}")
        raise
    
    # 3. Imprimir queries de análise
    logger.info("\n📊 FASE 3: Queries de análise disponíveis:")
    print_analysis_queries()
    
    logger.info("\n✅ Pipeline Gold concluído com sucesso!")
    logger.info("="*80)

if __name__ == "__main__":
    main()