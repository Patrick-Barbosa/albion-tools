# =============================================================================
# SILVER LAYER: Albion Online Market Data Transformation (ELT Strategy)
# =============================================================================
# Estratégia: Transform - Normalização Star Schema + Métricas Calculadas
# - Lê dados do Bronze (raw_json)
# - Parse completo de todos os campos
# - Cria dimensões (items, locations, quality)
# - Cria fatos com histórico completo por timestamp
# - Calcula métricas derivadas (spread, volatility, trends)
# - MERGE incremental (idempotente)
# - Checkpoint para rastrear progresso
# =============================================================================

import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, lit, current_timestamp, to_timestamp,
    when, coalesce, regexp_extract, 
    md5, concat_ws,
    lag, lead,
    row_number, dense_rank
)
from pyspark.sql.window import Window
from pyspark.sql.types import (
    StructType, StructField,
    StringType, LongType, IntegerType,
    DoubleType, BooleanType, TimestampType, DateType
)
from delta.tables import DeltaTable

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

class Config:
    """Configurações centralizadas do pipeline Silver"""
    
    # Unity Catalog
    CATALOG = "main"
    SCHEMA_BRONZE = "bronze"
    SCHEMA_SILVER = "silver"
    
    # Tabelas Bronze (source)
    BRONZE_MARKET_ORDERS = f"{CATALOG}.{SCHEMA_BRONZE}.market_orders_raw"
    BRONZE_MARKET_HISTORY = f"{CATALOG}.{SCHEMA_BRONZE}.market_history_raw"
    
    # Dimensões Silver
    DIM_ITEMS = f"{CATALOG}.{SCHEMA_SILVER}.dim_items"
    DIM_LOCATIONS = f"{CATALOG}.{SCHEMA_SILVER}.dim_locations"
    DIM_QUALITY = f"{CATALOG}.{SCHEMA_SILVER}.dim_quality"
    
    # Fatos Silver
    FACT_MARKET_ORDERS = f"{CATALOG}.{SCHEMA_SILVER}.fact_market_orders"
    FACT_MARKET_HISTORY = f"{CATALOG}.{SCHEMA_SILVER}.fact_market_history"
    
    # Checkpoint (para processamento incremental)
    CHECKPOINT_TABLE = f"{CATALOG}.{SCHEMA_SILVER}._checkpoints"
    
    # Thresholds para métricas
    PROFITABLE_SPREAD_PCT = 5.0  # 5% spread mínimo para ser "lucrativo"
    MARKET_TAX_PCT = 0.065  # 6.5% taxa de mercado do Albion
    
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
    COMMENT 'Checkpoints para processamento incremental Silver'
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
# DDL: CRIAÇÃO DAS DIMENSÕES
# =============================================================================

def create_silver_dimensions(spark: SparkSession) -> None:
    """Cria as dimensões do Star Schema"""
    logger.info("Criando schema Silver...")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {Config.CATALOG}.{Config.SCHEMA_SILVER}")
    
    # =========================================================================
    # dim_items
    # =========================================================================
    logger.info(f"Criando dimensão {Config.DIM_ITEMS}...")
    
    ddl_items = f"""
    CREATE TABLE IF NOT EXISTS {Config.DIM_ITEMS} (
      item_id STRING,
      item_name STRING COMMENT 'Nome do item (extrair do game data futuro)',
      tier INT COMMENT 'Tier extraído do item_id (T4 -> 4)',
      enchantment INT COMMENT 'Enchantment level (@0, @1, @2, @3)',
      category STRING COMMENT 'Categoria: Resource, Gear, Consumable, etc',
      is_artifact BOOLEAN COMMENT 'Se é item de artefato',
      created_at TIMESTAMP,
      updated_at TIMESTAMP,
      
      CONSTRAINT pk_items PRIMARY KEY (item_id)
    ) USING DELTA
    CLUSTER BY (tier, category)
    COMMENT 'Dimensão de itens do Albion Online'
    """
    spark.sql(ddl_items)
    logger.info(f"✅ Dimensão {Config.DIM_ITEMS} criada/verificada")
    
    # =========================================================================
    # dim_locations
    # =========================================================================
    logger.info(f"Criando dimensão {Config.DIM_LOCATIONS}...")
    
    ddl_locations = f"""
    CREATE TABLE IF NOT EXISTS {Config.DIM_LOCATIONS} (
      location_id STRING,
      location_name STRING,
      location_type STRING COMMENT 'City, BlackMarket, etc',
      region STRING COMMENT 'Royal, Outlands, etc',
      is_market_enabled BOOLEAN,
      created_at TIMESTAMP,
      updated_at TIMESTAMP,
      
      CONSTRAINT pk_locations PRIMARY KEY (location_id)
    ) USING DELTA
    CLUSTER BY (location_type, region)
    COMMENT 'Dimensão de localizações do Albion Online'
    """
    spark.sql(ddl_locations)
    logger.info(f"✅ Dimensão {Config.DIM_LOCATIONS} criada/verificada")
    
    # =========================================================================
    # dim_quality
    # =========================================================================
    logger.info(f"Criando dimensão {Config.DIM_QUALITY}...")
    
    ddl_quality = f"""
    CREATE TABLE IF NOT EXISTS {Config.DIM_QUALITY} (
      quality_id INT,
      quality_name STRING,
      quality_bonus_pct DOUBLE COMMENT 'Bonus de stats',
      created_at TIMESTAMP,
      
      CONSTRAINT pk_quality PRIMARY KEY (quality_id)
    ) USING DELTA
    COMMENT 'Dimensão de qualidade de itens'
    """
    spark.sql(ddl_quality)
    logger.info(f"✅ Dimensão {Config.DIM_QUALITY} criada/verificada")
    
    # Popular dim_quality com valores conhecidos
    populate_quality_dimension(spark)

def populate_quality_dimension(spark: SparkSession) -> None:
    """Popula dimensão de qualidade com valores do Albion Online"""
    logger.info("Populando dim_quality...")
    
    quality_data = [
        (1, "Normal", 0.0),
        (2, "Good", 10.0),
        (3, "Outstanding", 20.0),
        (4, "Excellent", 30.0),
        (5, "Masterpiece", 40.0)
    ]
    
    df = spark.createDataFrame(
        quality_data,
        ["quality_id", "quality_name", "quality_bonus_pct"]
    ).withColumn("created_at", current_timestamp())
    
    # MERGE para não duplicar
    DeltaTable.createOrReplace(spark) \
        .tableName(Config.DIM_QUALITY) \
        .addColumns(df.schema) \
        .execute()
    
    df.write.format("delta").mode("overwrite").saveAsTable(Config.DIM_QUALITY)
    logger.info("✅ dim_quality populada")

# =============================================================================
# DDL: CRIAÇÃO DAS TABELAS FATO
# =============================================================================

def create_silver_facts(spark: SparkSession) -> None:
    """Cria as tabelas fato do Star Schema"""
    
    # =========================================================================
    # fact_market_orders
    # =========================================================================
    logger.info(f"Criando fato {Config.FACT_MARKET_ORDERS}...")
    
    ddl_orders = f"""
    CREATE TABLE IF NOT EXISTS {Config.FACT_MARKET_ORDERS} (
      -- Chave natural (hash de item_id + city + quality + timestamp)
      order_id STRING,
      
      -- Foreign Keys (dimensões)
      item_id STRING,
      city STRING,
      quality INT,
      
      -- Métricas originais
      sell_price_min BIGINT,
      sell_price_max BIGINT,
      sell_price_min_date TIMESTAMP,
      sell_price_max_date TIMESTAMP,
      buy_price_min BIGINT,
      buy_price_max BIGINT,
      buy_price_min_date TIMESTAMP,
      buy_price_max_date TIMESTAMP,
      
      -- Métricas calculadas
      spread BIGINT COMMENT 'sell_price_min - buy_price_max',
      spread_pct DOUBLE COMMENT 'Spread percentual',
      mid_price BIGINT COMMENT 'Preço médio',
      price_range BIGINT COMMENT 'Volatilidade (max - min)',
      volatility_pct DOUBLE COMMENT 'Volatilidade percentual',
      is_profitable BOOLEAN COMMENT 'Spread > threshold',
      tax_amount BIGINT COMMENT 'Taxa de mercado estimada',
      net_profit BIGINT COMMENT 'Lucro líquido estimado',
      
      -- Timestamps
      market_timestamp TIMESTAMP,
      ingestion_timestamp TIMESTAMP,
      processing_timestamp TIMESTAMP,
      
      -- Metadados
      source_topic STRING,
      _bronze_ingestion_date DATE,
      
      CONSTRAINT pk_orders PRIMARY KEY (order_id)
    ) USING DELTA
    CLUSTER BY (ingestion_timestamp, city, item_id)
    TBLPROPERTIES (
      'delta.enableChangeDataFeed' = 'true',
      'delta.autoOptimize.optimizeWrite' = 'true'
    )
    COMMENT 'Fato de market orders com histórico completo e métricas'
    """
    spark.sql(ddl_orders)
    logger.info(f"✅ Fato {Config.FACT_MARKET_ORDERS} criado/verificado")
    
    # =========================================================================
    # fact_market_history
    # =========================================================================
    logger.info(f"Criando fato {Config.FACT_MARKET_HISTORY}...")
    
    ddl_history = f"""
    CREATE TABLE IF NOT EXISTS {Config.FACT_MARKET_HISTORY} (
      -- Chave natural
      history_id STRING,
      
      -- Foreign Keys
      item_id STRING,
      location STRING,
      quality INT,
      
      -- Métricas originais
      item_count BIGINT COMMENT 'Volume transacionado',
      avg_price BIGINT COMMENT 'Preço médio',
      timestamp TIMESTAMP,
      
      -- Métricas calculadas
      total_volume BIGINT COMMENT 'Volume financeiro total',
      price_per_unit BIGINT COMMENT 'Preço por unidade',
      velocity DOUBLE COMMENT 'Itens por hora',
      
      -- Comparação temporal (calculado via window)
      prev_avg_price BIGINT,
      price_change BIGINT,
      price_change_pct DOUBLE,
      trend STRING COMMENT 'UP, DOWN, STABLE',
      
      -- Timestamps
      market_timestamp TIMESTAMP,
      ingestion_timestamp TIMESTAMP,
      processing_timestamp TIMESTAMP,
      
      -- Metadados
      source_topic STRING,
      _bronze_ingestion_date DATE,
      
      CONSTRAINT pk_history PRIMARY KEY (history_id)
    ) USING DELTA
    CLUSTER BY (ingestion_timestamp, location, item_id)
    TBLPROPERTIES (
      'delta.enableChangeDataFeed' = 'true',
      'delta.autoOptimize.optimizeWrite' = 'true'
    )
    COMMENT 'Fato de market history com agregações e trends'
    """
    spark.sql(ddl_history)
    logger.info(f"✅ Fato {Config.FACT_MARKET_HISTORY} criado/verificado")

# =============================================================================
# PARSE & TRANSFORMATION: MARKET ORDERS
# =============================================================================

def parse_market_order(raw_json: str) -> Dict[str, Any]:
    """
    Parse completo do JSON de market orders.
    Extrai TODOS os campos + adiciona campos derivados.
    """
    try:
        data = json.loads(raw_json)
        
        # Campos originais
        item_id = data.get('item_id', 'UNKNOWN')
        city = data.get('city', 'UNKNOWN')
        quality = data.get('quality', 1)
        
        sell_price_min = data.get('sell_price_min', 0)
        sell_price_max = data.get('sell_price_max', 0)
        buy_price_min = data.get('buy_price_min', 0)
        buy_price_max = data.get('buy_price_max', 0)
        
        # Timestamps (podem vir como string ISO ou null)
        sell_min_date = data.get('sell_price_min_date')
        sell_max_date = data.get('sell_price_max_date')
        buy_min_date = data.get('buy_price_min_date')
        buy_max_date = data.get('buy_price_max_date')
        
        # Gerar order_id (hash único)
        order_id = hashlib.md5(
            f"{item_id}|{city}|{quality}|{sell_min_date}".encode()
        ).hexdigest()
        
        return {
            'order_id': order_id,
            'item_id': item_id,
            'city': city,
            'quality': quality,
            'sell_price_min': sell_price_min,
            'sell_price_max': sell_price_max,
            'sell_price_min_date': sell_min_date,
            'sell_price_max_date': sell_max_date,
            'buy_price_min': buy_price_min,
            'buy_price_max': buy_price_max,
            'buy_price_min_date': buy_min_date,
            'buy_price_max_date': buy_max_date
        }
        
    except Exception as e:
        logger.warning(f"Erro ao fazer parse de market order: {e}")
        return None

def calculate_order_metrics(df: DataFrame) -> DataFrame:
    """
    Calcula métricas derivadas para market orders.
    Recebe DataFrame com campos básicos, retorna com métricas calculadas.
    """
    return df \
        .withColumn("spread", col("sell_price_min") - col("buy_price_max")) \
        .withColumn("mid_price", (col("sell_price_min") + col("buy_price_max")) / 2) \
        .withColumn(
            "spread_pct",
            when(col("buy_price_max") > 0, (col("spread") / col("buy_price_max")) * 100).otherwise(0.0)
        ) \
        .withColumn("price_range", col("sell_price_max") - col("buy_price_min")) \
        .withColumn(
            "volatility_pct",
            when(col("mid_price") > 0, (col("price_range") / col("mid_price")) * 100).otherwise(0.0)
        ) \
        .withColumn(
            "is_profitable",
            (col("spread") > 0) & (col("spread_pct") > lit(Config.PROFITABLE_SPREAD_PCT))
        ) \
        .withColumn("tax_amount", (col("sell_price_min") * lit(Config.MARKET_TAX_PCT)).cast("bigint")) \
        .withColumn("net_profit", col("spread") - col("tax_amount")) \
        .withColumn("processing_timestamp", current_timestamp())

# =============================================================================
# PARSE & TRANSFORMATION: MARKET HISTORY
# =============================================================================

def parse_market_history(raw_json: str) -> Dict[str, Any]:
    """
    Parse completo do JSON de market history.
    Extrai TODOS os campos.
    """
    try:
        data = json.loads(raw_json)
        
        item_id = data.get('item_id', 'UNKNOWN')
        location = data.get('location', 'UNKNOWN')
        quality = data.get('quality', 1)
        item_count = data.get('item_count', 0)
        avg_price = data.get('data', [{}])[0].get('avg_price', 0) if data.get('data') else 0
        timestamp = data.get('data', [{}])[0].get('timestamp') if data.get('data') else None
        
        # Gerar history_id
        history_id = hashlib.md5(
            f"{item_id}|{location}|{quality}|{timestamp}".encode()
        ).hexdigest()
        
        return {
            'history_id': history_id,
            'item_id': item_id,
            'location': location,
            'quality': quality,
            'item_count': item_count,
            'avg_price': avg_price,
            'timestamp': timestamp
        }
        
    except Exception as e:
        logger.warning(f"Erro ao fazer parse de market history: {e}")
        return None

def calculate_history_metrics(df: DataFrame) -> DataFrame:
    """
    Calcula métricas derivadas para market history.
    Inclui comparação temporal via window functions.
    """
    # Window para calcular preço anterior
    window_spec = Window.partitionBy("item_id", "location", "quality").orderBy("timestamp")
    
    df_with_prev = df \
        .withColumn("prev_avg_price", lag("avg_price", 1).over(window_spec)) \
        .withColumn("total_volume", col("item_count") * col("avg_price")) \
        .withColumn("price_per_unit", col("avg_price")) \
        .withColumn("velocity", col("item_count") / lit(24.0))  # Assumindo time-scale de 24h
    
    # Calcular mudanças de preço
    df_with_changes = df_with_prev \
        .withColumn(
            "price_change",
            when(col("prev_avg_price").isNotNull(), col("avg_price") - col("prev_avg_price")).otherwise(0)
        ) \
        .withColumn(
            "price_change_pct",
            when(
                (col("prev_avg_price").isNotNull()) & (col("prev_avg_price") > 0),
                (col("price_change") / col("prev_avg_price")) * 100
            ).otherwise(0.0)
        ) \
        .withColumn(
            "trend",
            when(col("price_change_pct") > 5.0, lit("UP"))
            .when(col("price_change_pct") < -5.0, lit("DOWN"))
            .otherwise(lit("STABLE"))
        ) \
        .withColumn("processing_timestamp", current_timestamp())
    
    return df_with_changes

# =============================================================================
# ENRIQUECIMENTO DE DIMENSÕES
# =============================================================================

def enrich_item_dimension(spark: SparkSession, item_ids: List[str]) -> None:
    """
    Enriquece dimensão de itens com novos item_ids descobertos.
    Extrai tier e enchantment do item_id.
    """
    if not item_ids:
        return
    
    logger.info(f"Enriquecendo dim_items com {len(item_ids)} itens...")
    
    # Criar DataFrame de novos itens
    new_items = []
    for item_id in item_ids:
        # Extrair tier (T4, T5, etc)
        tier_match = item_id[1:2] if item_id.startswith('T') and len(item_id) > 1 else '0'
        tier = int(tier_match) if tier_match.isdigit() else 0
        
        # Extrair enchantment (@1, @2, etc)
        enchantment = 0
        if '@' in item_id:
            ench_str = item_id.split('@')[1]
            enchantment = int(ench_str) if ench_str.isdigit() else 0
        
        # Categoria simplificada (pode ser melhorada com mapeamento completo)
        category = "UNKNOWN"
        if "LEATHER" in item_id or "HIDE" in item_id:
            category = "Resource"
        elif "WOOD" in item_id or "PLANKS" in item_id:
            category = "Resource"
        elif "ORE" in item_id or "METALBAR" in item_id:
            category = "Resource"
        elif "FIBER" in item_id or "CLOTH" in item_id:
            category = "Resource"
        
        is_artifact = "_AVALON_" in item_id or "_UNDEAD_" in item_id
        
        new_items.append((
            item_id,
            item_id,  # item_name = item_id por enquanto
            tier,
            enchantment,
            category,
            is_artifact,
            datetime.now(),
            datetime.now()
        ))
    
    df_new = spark.createDataFrame(
        new_items,
        ["item_id", "item_name", "tier", "enchantment", "category", "is_artifact", "created_at", "updated_at"]
    )
    
    # MERGE na dimensão
    delta_table = DeltaTable.forName(spark, Config.DIM_ITEMS)
    
    delta_table.alias("target").merge(
        df_new.alias("source"),
        "target.item_id = source.item_id"
    ).whenNotMatchedInsertAll().execute()
    
    logger.info(f"✅ dim_items enriquecida")

def enrich_location_dimension(spark: SparkSession, locations: List[str]) -> None:
    """
    Enriquece dimensão de localizações com novos locations descobertos.
    """
    if not locations:
        return
    
    logger.info(f"Enriquecendo dim_locations com {len(locations)} localizações...")
    
    # Mapeamento de localizações conhecidas
    location_types = {
        "Caerleon": ("City", "Royal"),
        "Bridgewatch": ("City", "Royal"),
        "Lymhurst": ("City", "Royal"),
        "Martlock": ("City", "Royal"),
        "Thetford": ("City", "Royal"),
        "Fort Sterling": ("City", "Royal"),
        "Black Market": ("BlackMarket", "Royal")
    }
    
    new_locations = []
    for location in locations:
        loc_type, region = location_types.get(location, ("Unknown", "Unknown"))
        
        new_locations.append((
            location,
            location,
            loc_type,
            region,
            True,  # is_market_enabled
            datetime.now(),
            datetime.now()
        ))
    
    df_new = spark.createDataFrame(
        new_locations,
        ["location_id", "location_name", "location_type", "region", "is_market_enabled", "created_at", "updated_at"]
    )
    
    # MERGE na dimensão
    delta_table = DeltaTable.forName(spark, Config.DIM_LOCATIONS)
    
    delta_table.alias("target").merge(
        df_new.alias("source"),
        "target.location_id = source.location_id"
    ).whenNotMatchedInsertAll().execute()
    
    logger.info(f"✅ dim_locations enriquecida")

# =============================================================================
# PROCESSAMENTO INCREMENTAL: MARKET ORDERS
# =============================================================================

def process_incremental_orders(spark: SparkSession) -> None:
    """
    Processa market orders do Bronze para Silver de forma incremental.
    Usa checkpoint para processar apenas novos dados.
    """
    pipeline_name = "market_orders_bronze_to_silver"
    logger.info(f"🚀 Iniciando processamento incremental: {pipeline_name}")
    
    # Obter checkpoint
    last_checkpoint = get_checkpoint(spark, pipeline_name)
    
    if last_checkpoint:
        logger.info(f"📌 Checkpoint encontrado: {last_checkpoint}")
        where_clause = f"ingestion_timestamp > '{last_checkpoint}'"
    else:
        logger.info("📌 Primeiro processamento (sem checkpoint)")
        where_clause = "1=1"
    
    # Ler dados Bronze incrementais
    df_bronze = spark.sql(f"""
        SELECT 
            raw_json,
            item_id,
            city,
            source_topic,
            ingestion_timestamp,
            ingestion_date
        FROM {Config.BRONZE_MARKET_ORDERS}
        WHERE {where_clause}
    """)
    
    count = df_bronze.count()
    if count == 0:
        logger.info("✅ Nenhum dado novo para processar")
        return
    
    logger.info(f"📊 Processando {count} registros novos")
    
    # Parse JSON usando PySpark (mais eficiente que UDF Python)
    from pyspark.sql.functions import from_json
    
    schema = StructType([
        StructField("item_id", StringType()),
        StructField("city", StringType()),
        StructField("quality", IntegerType()),
        StructField("sell_price_min", LongType()),
        StructField("sell_price_max", LongType()),
        StructField("sell_price_min_date", StringType()),
        StructField("sell_price_max_date", StringType()),
        StructField("buy_price_min", LongType()),
        StructField("buy_price_max", LongType()),
        StructField("buy_price_min_date", StringType()),
        StructField("buy_price_max_date", StringType())
    ])
    
    df_parsed = df_bronze.withColumn("data", from_json(col("raw_json"), schema)) \
        .select(
            md5(concat_ws("|", col("data.item_id"), col("data.city"), col("data.quality"), col("data.sell_price_min_date"))).alias("order_id"),
            col("data.item_id").alias("item_id"),
            col("data.city").alias("city"),
            coalesce(col("data.quality"), lit(1)).alias("quality"),
            coalesce(col("data.sell_price_min"), lit(0)).alias("sell_price_min"),
            coalesce(col("data.sell_price_max"), lit(0)).alias("sell_price_max"),
            to_timestamp(col("data.sell_price_min_date")).alias("sell_price_min_date"),
            to_timestamp(col("data.sell_price_max_date")).alias("sell_price_max_date"),
            coalesce(col("data.buy_price_min"), lit(0)).alias("buy_price_min"),
            coalesce(col("data.buy_price_max"), lit(0)).alias("buy_price_max"),
            to_timestamp(col("data.buy_price_min_date")).alias("buy_price_min_date"),
            to_timestamp(col("data.buy_price_max_date")).alias("buy_price_max_date"),
            col("source_topic"),
            col("ingestion_timestamp"),
            col("ingestion_date").alias("_bronze_ingestion_date"),
            coalesce(to_timestamp(col("data.sell_price_min_date")), col("ingestion_timestamp")).alias("market_timestamp")
        )
    
    # Calcular métricas
    df_enriched = calculate_order_metrics(df_parsed)
    
    # Enriquecer dimensões
    item_ids = [row.item_id for row in df_enriched.select("item_id").distinct().collect()]
    cities = [row.city for row in df_enriched.select("city").distinct().collect()]
    
    enrich_item_dimension(spark, item_ids)
    enrich_location_dimension(spark, cities)
    
    # MERGE na tabela fato
    logger.info(f"💾 Fazendo MERGE em {Config.FACT_MARKET_ORDERS}...")
    
    delta_table = DeltaTable.forName(spark, Config.FACT_MARKET_ORDERS)
    
    delta_table.alias("target").merge(
        df_enriched.alias("source"),
        "target.order_id = source.order_id"
    ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
    
    # Atualizar checkpoint
    max_timestamp = df_bronze.agg({"ingestion_timestamp": "max"}).collect()[0][0]
    update_checkpoint(spark, pipeline_name, max_timestamp, count)
    
    logger.info(f"✅ Processamento concluído: {count} registros")

# =============================================================================
# PROCESSAMENTO INCREMENTAL: MARKET HISTORY
# =============================================================================

def process_incremental_history(spark: SparkSession) -> None:
    """
    Processa market history do Bronze para Silver de forma incremental.
    """
    pipeline_name = "market_history_bronze_to_silver"
    logger.info(f"🚀 Iniciando processamento incremental: {pipeline_name}")
    
    # Obter checkpoint
    last_checkpoint = get_checkpoint(spark, pipeline_name)
    
    if last_checkpoint:
        logger.info(f"📌 Checkpoint encontrado: {last_checkpoint}")
        where_clause = f"ingestion_timestamp > '{last_checkpoint}'"
    else:
        logger.info("📌 Primeiro processamento (sem checkpoint)")
        where_clause = "1=1"
    
    # Ler dados Bronze incrementais
    df_bronze = spark.sql(f"""
        SELECT 
            raw_json,
            item_id,
            location,
            source_topic,
            ingestion_timestamp,
            ingestion_date
        FROM {Config.BRONZE_MARKET_HISTORY}
        WHERE {where_clause}
    """)
    
    count = df_bronze.count()
    if count == 0:
        logger.info("✅ Nenhum dado novo para processar")
        return
    
    logger.info(f"📊 Processando {count} registros novos")
    
    # Parse JSON usando PySpark
    from pyspark.sql.functions import from_json, explode
    
    schema = StructType([
        StructField("item_id", StringType()),
        StructField("location", StringType()),
        StructField("quality", IntegerType()),
        StructField("data", StructType([
            StructField("item_count", LongType()),
            StructField("avg_price", LongType()),
            StructField("timestamp", StringType())
        ]))
    ])
    
    df_parsed = df_bronze.withColumn("parsed", from_json(col("raw_json"), schema)) \
        .select(
            md5(concat_ws("|", col("parsed.item_id"), col("parsed.location"), col("parsed.quality"), col("parsed.data.timestamp"))).alias("history_id"),
            col("parsed.item_id").alias("item_id"),
            col("parsed.location").alias("location"),
            coalesce(col("parsed.quality"), lit(1)).alias("quality"),
            coalesce(col("parsed.data.item_count"), lit(0)).alias("item_count"),
            coalesce(col("parsed.data.avg_price"), lit(0)).alias("avg_price"),
            to_timestamp(col("parsed.data.timestamp")).alias("timestamp"),
            col("source_topic"),
            col("ingestion_timestamp"),
            col("ingestion_date").alias("_bronze_ingestion_date"),
            coalesce(to_timestamp(col("parsed.data.timestamp")), col("ingestion_timestamp")).alias("market_timestamp")
        )
    
    # Calcular métricas
    df_enriched = calculate_history_metrics(df_parsed)
    
    # Enriquecer dimensões
    item_ids = [row.item_id for row in df_enriched.select("item_id").distinct().collect()]
    locations = [row.location for row in df_enriched.select("location").distinct().collect()]
    
    enrich_item_dimension(spark, item_ids)
    enrich_location_dimension(spark, locations)
    
    # MERGE na tabela fato
    logger.info(f"💾 Fazendo MERGE em {Config.FACT_MARKET_HISTORY}...")
    
    delta_table = DeltaTable.forName(spark, Config.FACT_MARKET_HISTORY)
    
    delta_table.alias("target").merge(
        df_enriched.alias("source"),
        "target.history_id = source.history_id"
    ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
    
    # Atualizar checkpoint
    max_timestamp = df_bronze.agg({"ingestion_timestamp": "max"}).collect()[0][0]
    update_checkpoint(spark, pipeline_name, max_timestamp, count)
    
    logger.info(f"✅ Processamento concluído: {count} registros")

# =============================================================================
# MAIN: PONTO DE ENTRADA
# =============================================================================

def main():
    """
    Ponto de entrada do pipeline Silver.
    Orquestra todo o processamento: dimensões + fatos.
    """
    logger.info("="*80)
    logger.info("SILVER LAYER: Albion Online Market Data Transformation")
    logger.info("Estratégia: Star Schema + Métricas Calculadas + MERGE Incremental")
    logger.info("="*80)
    
    # Criar SparkSession
    spark = SparkSession.builder \
        .appName("Silver-Albion-Market-Transformation") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .getOrCreate()
    
    logger.info(f"✅ Spark Session criada: {spark.version}")
    
    # 1. Criar estrutura Silver
    logger.info("\n📐 FASE 1: Criando estrutura Silver...")
    create_checkpoint_table(spark)
    create_silver_dimensions(spark)
    create_silver_facts(spark)
    
    # 2. Processar Market Orders
    logger.info("\n📊 FASE 2: Processando Market Orders (Bronze → Silver)...")
    try:
        process_incremental_orders(spark)
    except Exception as e:
        logger.error(f"❌ Erro ao processar market orders: {e}")
    
    # 3. Processar Market History
    logger.info("\n📈 FASE 3: Processando Market History (Bronze → Silver)...")
    try:
        process_incremental_history(spark)
    except Exception as e:
        logger.error(f"❌ Erro ao processar market history: {e}")
    
    logger.info("\n✅ Pipeline Silver concluído com sucesso!")
    logger.info("="*80)

if __name__ == "__main__":
    main()
