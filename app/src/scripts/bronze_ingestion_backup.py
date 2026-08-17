# =============================================================================
# BRONZE LAYER: Albion Online Market Data Ingestion (ELT Strategy)
# =============================================================================
# Estratégia: Extract + Load com transformações mínimas
# - Consome streams NATS em tempo real
# - Parse JSON mínimo (apenas para clustering)
# - Armazena raw_json completo
# - SEM filtros (todas cidades, todos itens)
# - SEM deduplicação (tratado na Silver)
# - Append-only (delta.appendOnly = true)
# =============================================================================

import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import logging

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    current_timestamp,
    current_date,
    lit,
    col,
    from_json,
    get_json_object,
    to_timestamp
)
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    LongType,
    IntegerType,
    TimestampType
)
from delta.tables import DeltaTable

# Para NATS streaming
try:
    from nats.aio.client import Client as NATS
except ImportError:
    print("AVISO: nats-py não instalado. Instalar com: pip install nats-py")
    NATS = None

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

class Config:
    """Configurações centralizadas do pipeline"""
    
    # Unity Catalog
    CATALOG = "main"
    SCHEMA = "bronze"
    
    # Tabelas
    TABLE_MARKET_ORDERS = f"{CATALOG}.{SCHEMA}.market_orders_raw"
    TABLE_MARKET_HISTORY = f"{CATALOG}.{SCHEMA}.market_history_raw"
    
    # NATS Configuration
    NATS_SERVER = "nats://public:thenewalbiondata@nats.albion-online-data.com:4222"
    
    # Topics NATS (deduplicados no servidor)
    TOPIC_MARKET_ORDERS = "marketorders.deduped"
    TOPIC_MARKET_HISTORY = "markethistories.deduped"
    
    # Checkpoints (para Structured Streaming)
    CHECKPOINT_LOCATION_ORDERS = f"/tmp/checkpoints/{SCHEMA}/market_orders"
    CHECKPOINT_LOCATION_HISTORY = f"/tmp/checkpoints/{SCHEMA}/market_history"
    
    # Batch settings
    BATCH_SIZE = 1000  # Mensagens por micro-batch
    TRIGGER_INTERVAL = "30 seconds"  # Processar a cada 30s
    
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
# DDL: CRIAÇÃO DAS TABELAS BRONZE
# =============================================================================

def create_bronze_tables(spark: SparkSession) -> None:
    """
    Cria as tabelas Bronze se não existirem.
    Estratégia ELT: Schema mínimo + raw_json para flexibilidade máxima.
    """
    logger.info("Criando schema Bronze...")
    
    # Criar schema se não existir
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {Config.CATALOG}.{Config.SCHEMA}")
    
    # ==========================================================================
    # Tabela 1: market_orders_raw
    # ==========================================================================
    logger.info(f"Criando tabela {Config.TABLE_MARKET_ORDERS}...")
    
    ddl_market_orders = f"""
    CREATE TABLE IF NOT EXISTS {Config.TABLE_MARKET_ORDERS} (
      -- Metadados de ingestão
      ingestion_timestamp TIMESTAMP COMMENT 'Momento da captura do evento',
      ingestion_date DATE COMMENT 'Data da captura (partição)',
      source_topic STRING COMMENT 'Tópico NATS de origem',
      
      -- Payload completo (ELT: armazenar tudo)
      raw_json STRING COMMENT 'JSON original completo sem parsing',
      
      -- Campos mínimos extraídos (APENAS para clustering/performance)
      item_id STRING COMMENT 'ID do item extraído (ex: T4_LEATHER)',
      city STRING COMMENT 'Cidade extraída (ex: Caerleon)'
    )
    USING DELTA
    CLUSTER BY (ingestion_date, city, item_id)
    TBLPROPERTIES (
      'delta.enableChangeDataFeed' = 'true',
      'delta.appendOnly' = 'true',
      'delta.autoOptimize.optimizeWrite' = 'true',
      'delta.autoOptimize.autoCompact' = 'true'
    )
    COMMENT 'BRONZE RAW: Market orders sem transformações (estratégia ELT)'
    """
    
    spark.sql(ddl_market_orders)
    logger.info(f"✅ Tabela {Config.TABLE_MARKET_ORDERS} criada/verificada")
    
    # ==========================================================================
    # Tabela 2: market_history_raw
    # ==========================================================================
    logger.info(f"Criando tabela {Config.TABLE_MARKET_HISTORY}...")
    
    ddl_market_history = f"""
    CREATE TABLE IF NOT EXISTS {Config.TABLE_MARKET_HISTORY} (
      -- Metadados de ingestão
      ingestion_timestamp TIMESTAMP COMMENT 'Momento da captura do evento',
      ingestion_date DATE COMMENT 'Data da captura (partição)',
      source_topic STRING COMMENT 'Tópico NATS de origem',
      
      -- Payload completo (ELT: armazenar tudo)
      raw_json STRING COMMENT 'JSON original completo sem parsing',
      
      -- Campos mínimos extraídos (APENAS para clustering/performance)
      item_id STRING COMMENT 'ID do item extraído',
      location STRING COMMENT 'Localização extraída'
    )
    USING DELTA
    CLUSTER BY (ingestion_date, location, item_id)
    TBLPROPERTIES (
      'delta.enableChangeDataFeed' = 'true',
      'delta.appendOnly' = 'true',
      'delta.autoOptimize.optimizeWrite' = 'true',
      'delta.autoOptimize.autoCompact' = 'true'
    )
    COMMENT 'BRONZE RAW: Market history sem transformações (estratégia ELT)'
    """
    
    spark.sql(ddl_market_history)
    logger.info(f"✅ Tabela {Config.TABLE_MARKET_HISTORY} criada/verificada")

# =============================================================================
# FUNÇÕES DE INGESTÃO: PARSE MÍNIMO (ELT)
# =============================================================================

def parse_minimal_market_order(json_str: str) -> Dict[str, Any]:
    """
    Parse MÍNIMO para market orders.
    Extrai apenas item_id e city para clustering.
    Raw JSON preservado para transformações futuras na Silver.
    
    ELT: Transformações complexas ficam na Silver!
    """
    try:
        data = json.loads(json_str)
        return {
            'item_id': data.get('item_id', 'UNKNOWN'),
            'city': data.get('city', 'UNKNOWN'),
            'raw_json': json_str
        }
    except Exception as e:
        logger.warning(f"Erro ao fazer parse mínimo: {e}")
        return {
            'item_id': 'PARSE_ERROR',
            'city': 'PARSE_ERROR',
            'raw_json': json_str
        }

def parse_minimal_market_history(json_str: str) -> Dict[str, Any]:
    """
    Parse MÍNIMO para market history.
    Extrai apenas item_id e location para clustering.
    Raw JSON preservado para transformações futuras na Silver.
    
    ELT: Transformações complexas ficam na Silver!
    """
    try:
        data = json.loads(json_str)
        return {
            'item_id': data.get('item_id', 'UNKNOWN'),
            'location': data.get('location', 'UNKNOWN'),
            'raw_json': json_str
        }
    except Exception as e:
        logger.warning(f"Erro ao fazer parse mínimo: {e}")
        return {
            'item_id': 'PARSE_ERROR',
            'location': 'PARSE_ERROR',
            'raw_json': json_str
        }

# =============================================================================
# INGESTÃO VIA NATS (Async)
# =============================================================================

class NATSIngestion:
    """
    Classe para gerenciar ingestão via NATS streaming.
    Estratégia: Buffering em memória → Batch insert no Delta.
    """
    
    def __init__(self, spark: SparkSession):
        self.spark = spark
        self.nc = NATS() if NATS else None
        
        # Buffers para batch insert
        self.orders_buffer = []
        self.history_buffer = []
        
        self.batch_size = Config.BATCH_SIZE
        
    async def connect(self):
        """Conecta ao servidor NATS"""
        if not self.nc:
            raise ImportError("nats-py não está instalado")
        
        logger.info(f"Conectando ao NATS: {Config.NATS_SERVER}")
        await self.nc.connect(Config.NATS_SERVER)
        logger.info("✅ Conectado ao NATS")
    
    async def message_handler_orders(self, msg):
        """
        Handler para mensagens de market orders.
        Parse mínimo + buffer.
        """
        try:
            json_str = msg.data.decode()
            
            # Parse mínimo (ELT!)
            parsed = parse_minimal_market_order(json_str)
            
            # Adicionar metadados
            record = {
                'ingestion_timestamp': datetime.now(),
                'ingestion_date': datetime.now().date(),
                'source_topic': Config.TOPIC_MARKET_ORDERS,
                **parsed
            }
            
            self.orders_buffer.append(record)
            
            # Flush se atingir batch size
            if len(self.orders_buffer) >= self.batch_size:
                await self.flush_orders()
                
        except Exception as e:
            logger.error(f"Erro no handler de orders: {e}")
    
    async def message_handler_history(self, msg):
        """
        Handler para mensagens de market history.
        Parse mínimo + buffer.
        """
        try:
            json_str = msg.data.decode()
            
            # Parse mínimo (ELT!)
            parsed = parse_minimal_market_history(json_str)
            
            # Adicionar metadados
            record = {
                'ingestion_timestamp': datetime.now(),
                'ingestion_date': datetime.now().date(),
                'source_topic': Config.TOPIC_MARKET_HISTORY,
                **parsed
            }
            
            self.history_buffer.append(record)
            
            # Flush se atingir batch size
            if len(self.history_buffer) >= self.batch_size:
                await self.flush_history()
                
        except Exception as e:
            logger.error(f"Erro no handler de history: {e}")
    
    async def flush_orders(self):
        """Flush buffer de orders para Delta table"""
        if not self.orders_buffer:
            return
        
        try:
            logger.info(f"Flushing {len(self.orders_buffer)} orders para Delta...")
            
            # Criar DataFrame
            df = self.spark.createDataFrame(self.orders_buffer)
            
            # Append to Delta (ELT: sem MERGE, só APPEND!)
            df.write \
                .format("delta") \
                .mode("append") \
                .saveAsTable(Config.TABLE_MARKET_ORDERS)
            
            logger.info(f"✅ {len(self.orders_buffer)} orders ingeridas")
            
            # Limpar buffer
            self.orders_buffer = []
            
        except Exception as e:
            logger.error(f"Erro ao fazer flush de orders: {e}")
    
    async def flush_history(self):
        """Flush buffer de history para Delta table"""
        if not self.history_buffer:
            return
        
        try:
            logger.info(f"Flushing {len(self.history_buffer)} history records para Delta...")
            
            # Criar DataFrame
            df = self.spark.createDataFrame(self.history_buffer)
            
            # Append to Delta (ELT: sem MERGE, só APPEND!)
            df.write \
                .format("delta") \
                .mode("append") \
                .saveAsTable(Config.TABLE_MARKET_HISTORY)
            
            logger.info(f"✅ {len(self.history_buffer)} history records ingeridos")
            
            # Limpar buffer
            self.history_buffer = []
            
        except Exception as e:
            logger.error(f"Erro ao fazer flush de history: {e}")
    
    async def subscribe(self):
        """Subscribe aos tópicos NATS"""
        logger.info(f"Subscribing to {Config.TOPIC_MARKET_ORDERS}...")
        await self.nc.subscribe(Config.TOPIC_MARKET_ORDERS, cb=self.message_handler_orders)
        
        logger.info(f"Subscribing to {Config.TOPIC_MARKET_HISTORY}...")
        await self.nc.subscribe(Config.TOPIC_MARKET_HISTORY, cb=self.message_handler_history)
        
        logger.info("✅ Subscribed to all topics")
    
    async def run(self):
        """Loop principal de ingestão"""
        await self.connect()
        await self.subscribe()
        
        logger.info("🚀 Pipeline Bronze iniciado. Aguardando mensagens...")
        
        try:
            # Keep alive loop
            while True:
                await asyncio.sleep(30)  # Flush periódico a cada 30s
                
                # Flush buffers pendentes
                if self.orders_buffer:
                    await self.flush_orders()
                if self.history_buffer:
                    await self.flush_history()
                    
        except KeyboardInterrupt:
            logger.info("⚠️  Interrupção detectada. Fazendo flush final...")
            await self.flush_orders()
            await self.flush_history()
            await self.nc.close()
            logger.info("✅ Pipeline encerrado")

# =============================================================================
# ALTERNATIVA: INGESTÃO VIA API REST (Batch)
# =============================================================================

def fetch_all_items() -> list:
    """
    Busca lista completa de itens do Albion Online.
    Retorna lista de item_ids para processar em batch.
    """
    import requests
    
    base_url = "https://west.albion-online-data.com"
    
    try:
        logger.info("Buscando lista completa de itens...")
        response = requests.get(f"{base_url}/api/v2/stats/prices.json", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # Extrair item_ids únicos
            item_ids = list(set([item['item_id'] for item in data if 'item_id' in item]))
            logger.info(f"✅ {len(item_ids)} itens únicos encontrados")
            return item_ids
        else:
            logger.warning(f"Erro ao buscar itens: {response.status_code}. Usando lista padrão.")
            return []
    except Exception as e:
        logger.error(f"Erro ao buscar lista de itens: {e}")
        return []

def ingest_batch_from_api(
    spark: SparkSession,
    item_ids: Optional[list] = None,
    locations: Optional[str] = None,
    batch_size: int = 50
) -> None:
    """
    VERSÃO OTIMIZADA PARA FREE EDITION.
    Busca TODOS os itens via API REST em batches paralelos.
    
    Estratégia:
    - Busca lista completa de itens (API /prices)
    - Divide em batches de N itens
    - Faz requests paralelos (ThreadPool)
    - Otimizado para serverless (10 min de execução)
    
    Args:
        spark: SparkSession
        item_ids: Lista de item_ids (se None, busca todos)
        locations: Localizações específicas (se None, usa todas)
        batch_size: Itens por batch (default 50)
    """
    import requests
    from datetime import datetime
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    base_url = "https://west.albion-online-data.com"
    
    logger.info("="*80)
    logger.info("INGESTÃO BATCH API REST - VERSÃO FREE EDITION OTIMIZADA")
    logger.info("="*80)
    
    # 1. Buscar lista completa de itens (se não fornecida)
    if not item_ids:
        logger.info("Buscando lista completa de itens via API...")
        item_ids = fetch_all_items()
        
        if not item_ids:
            # Fallback: lista de itens populares
            logger.warning("Usando lista padrão de itens populares")
            item_ids = [
                "T4_LEATHER", "T5_WOOD", "T6_ORE", "T4_HIDE", "T5_FIBER",
                "T4_ROCK", "T5_PLANKS", "T6_METALBAR", "T4_CLOTH", "T5_STONEBLOCK"
            ]
    
    logger.info(f"Total de itens para processar: {len(item_ids)}")
    logger.info(f"Dividindo em batches de {batch_size} itens...")
    
    # Dividir itens em batches
    item_batches = [item_ids[i:i + batch_size] for i in range(0, len(item_ids), batch_size)]
    logger.info(f"Total de batches: {len(item_batches)}")
    
    all_orders = []
    all_history = []
    
    def process_batch(batch_items, batch_num):
        """Processa um batch de itens"""
        try:
            # CORREÇÃO CRÍTICA: Join items com vírgula (formato esperado pela API)
            items_str = ','.join(batch_items)
            
            logger.info(f"  Batch {batch_num}/{len(item_batches)}: {len(batch_items)} itens")
            
            # 1. Current prices
            logger.info(f"    Buscando preços atuais...")
            url = f"{base_url}/api/v2/stats/prices/{items_str}.json"
    params = {}
    if locations:
        params['locations'] = locations
    
    response = requests.get(url, params=params, headers={'Accept-Encoding': 'gzip'})
    
    if response.status_code == 200:
        data = response.json()
        
        # Converter para formato Bronze
        records = []
        for item in data:
            records.append({
                'ingestion_timestamp': datetime.now(),
                'ingestion_date': datetime.now().date(),
                'source_topic': 'API_REST_BATCH',
                'raw_json': json.dumps(item),
                'item_id': item.get('item_id', 'UNKNOWN'),
                'city': item.get('city', 'UNKNOWN')
            })
        
        # Append to Delta
        if records:
            df = spark.createDataFrame(records)
            df.write.format("delta").mode("append").saveAsTable(Config.TABLE_MARKET_ORDERS)
            logger.info(f"✅ {len(records)} market orders ingeridos via API")
    else:
        logger.error(f"Erro na API: {response.status_code}")
    
    # 2. Historical data (últimos 7 dias)
    logger.info(f"Buscando histórico: {item_ids}...")
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    url = f"{base_url}/api/v2/stats/history/{item_ids}.json"
    params = {
        'date': start_date,
        'end_date': end_date,
        'time-scale': 24
    }
    if locations:
        params['locations'] = locations
    
    response = requests.get(url, params=params, headers={'Accept-Encoding': 'gzip'})
    
    if response.status_code == 200:
        data = response.json()
        
        # Converter para formato Bronze
        records = []
        for item in data:
            records.append({
                'ingestion_timestamp': datetime.now(),
                'ingestion_date': datetime.now().date(),
                'source_topic': 'API_REST_BATCH',
                'raw_json': json.dumps(item),
                'item_id': item.get('item_id', 'UNKNOWN'),
                'location': item.get('location', 'UNKNOWN')
            })
        
        # Append to Delta
        if records:
            df = spark.createDataFrame(records)
            df.write.format("delta").mode("append").saveAsTable(Config.TABLE_MARKET_HISTORY)
            logger.info(f"✅ {len(records)} history records ingeridos via API")
    else:
        logger.error(f"Erro na API: {response.status_code}")

# =============================================================================
# MAIN: PONTO DE ENTRADA
# =============================================================================

def main(mode: str = "streaming"):
    """
    Ponto de entrada do pipeline Bronze.
    
    Args:
        mode: 'streaming' (NATS) ou 'batch' (API REST)
    """
    logger.info("="*80)
    logger.info("BRONZE LAYER: Albion Online Market Data Ingestion")
    logger.info("Estratégia: ELT (Extract + Load com transformações mínimas)")
    logger.info("="*80)
    
    # Criar SparkSession
    spark = SparkSession.builder \
        .appName("Bronze-Albion-Market-Ingestion") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .getOrCreate()
    
    logger.info(f"✅ Spark Session criada: {spark.version}")
    
    # Criar tabelas Bronze
    create_bronze_tables(spark)
    
    if mode == "streaming":
        logger.info("Modo: STREAMING (NATS)")
        
        # Iniciar ingestão via NATS
        ingestion = NATSIngestion(spark)
        
        # Run async loop
        asyncio.run(ingestion.run())
        
    elif mode == "batch":
        logger.info("Modo: BATCH (API REST)")
        
        # Ingestão batch via API
        ingest_batch_from_api(
            spark,
            item_ids=None,  # Todos os itens populares
            locations=None  # Todas as localizações
        )
        
        logger.info("✅ Ingestão batch concluída")
    
    else:
        raise ValueError(f"Modo inválido: {mode}. Use 'streaming' ou 'batch'")

# =============================================================================
# ENTRY POINT PARA DATABRICKS
# =============================================================================

if __name__ == "__main__":
    import sys
    
    # Detectar se está rodando no Databricks
    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.getOrCreate()
        logger.info("✅ Spark Session detectada (Databricks)")
        
        # Executar modo batch (otimizado para Free Edition)
        logger.info("="*80)
        logger.info("INICIANDO BRONZE INGESTION - FREE EDITION")
        logger.info("Modo: BATCH API REST (TODOS os itens)")
        logger.info("="*80)
        
        # 1. Criar tabelas
        create_bronze_tables(spark)
        
        # 2. Executar ingestão completa
        ingest_batch_from_api(
            spark=spark,
            item_ids=None,      # None = busca TODOS via API
            locations=None,     # None = todas as cidades
            batch_size=50       # Otimizado para rate limits
        )
        
        # 3. Exibir estatísticas
        logger.info("="*80)
        logger.info("VALIDAÇÃO PÓS-INGESTÃO")
        logger.info("="*80)
        
        orders_count = spark.sql(f"SELECT COUNT(*) as cnt FROM {Config.TABLE_MARKET_ORDERS}").collect()[0]['cnt']
        history_count = spark.sql(f"SELECT COUNT(*) as cnt FROM {Config.TABLE_MARKET_HISTORY}").collect()[0]['cnt']
        
        logger.info(f"Market Orders: {orders_count:,} registros")
        logger.info(f"Market History: {history_count:,} registros")
        logger.info(f"Total: {orders_count + history_count:,} registros")
        
        # Itens únicos
        unique_items = spark.sql(f"""
            SELECT COUNT(DISTINCT item_id) as cnt 
            FROM {Config.TABLE_MARKET_ORDERS}
        """).collect()[0]['cnt']
        
        logger.info(f"Itens únicos capturados: {unique_items:,}")
        logger.info("="*80)
        logger.info("✅ INGESTÃO COMPLETA COM SUCESSO!")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"❌ Erro na execução: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
