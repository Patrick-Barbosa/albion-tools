#!/usr/bin/env python3
# =============================================================================
# BRONZE LAYER: Albion Online Market Data Ingestion via NATS
# Real-time streaming ingestion for Medallion Architecture
# =============================================================================
"""
Ponto de entrada para ingestão Bronze via NATS streaming.

Este script:
1. Conecta ao broker NATS público do Albion Online
2. Consome mensagens em tempo real do tópico marketorders.deduped
3. Grava dados na tabela Bronze em micro-batches
4. Executa por um período configurável e então encerra gracefully

Uso:
    # Via Databricks Job
    databricks bundle run bronze_ingestion -t prod
    
    # Local (desenvolvimento)
    python bronze_ingestion.py --duration 3600 --buffer-size 1000
"""

import sys
import time
import signal
import argparse
import logging
from pathlib import Path

# Adicionar diretório raiz ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from nats.ingestion import NATSBronzeIngestion

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Bronze layer NATS ingestion for Albion Market Analysis'
    )
    
    parser.add_argument(
        '--catalog',
        default='main',
        help='Unity Catalog name (default: main)'
    )
    
    parser.add_argument(
        '--schema',
        default='bronze',
        help='Schema name (default: bronze)'
    )
    
    parser.add_argument(
        '--table',
        default='market_orders_raw',
        help='Table name (default: market_orders_raw)'
    )
    
    parser.add_argument(
        '--duration',
        type=int,
        default=600,  # 10 minutos por padrão
        help='Duration to run ingestion in seconds (default: 600)'
    )
    
    parser.add_argument(
        '--buffer-size',
        type=int,
        default=1000,
        help='Buffer size before auto-flush (default: 1000)'
    )
    
    parser.add_argument(
        '--flush-interval',
        type=int,
        default=30,
        help='Flush interval in seconds (default: 30)'
    )
    
    return parser.parse_args()


def main():
    """Main execution function."""
    args = parse_args()
    
    logger.info("="*80)
    logger.info("ALBION MARKET ANALYSIS - BRONZE LAYER NATS INGESTION")
    logger.info("="*80)
    logger.info(f"Catalog: {args.catalog}")
    logger.info(f"Schema: {args.schema}")
    logger.info(f"Table: {args.table}")
    logger.info(f"Duration: {args.duration}s")
    logger.info(f"Buffer size: {args.buffer_size}")
    logger.info(f"Flush interval: {args.flush_interval}s")
    logger.info("="*80)
    
    # Criar instância de ingestão
    ingestion = NATSBronzeIngestion(
        catalog_name=args.catalog,
        schema_name=args.schema,
        table_name=args.table,
        buffer_size=args.buffer_size,
        flush_interval_seconds=args.flush_interval,
    )
    
    # Setup signal handler para graceful shutdown
    def signal_handler(sig, frame):
        logger.info("\n🛑 Sinal de interrupção recebido. Parando ingestão...")
        ingestion.stop(timeout=60)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Iniciar ingestão
    logger.info("🚀 Iniciando ingestão NATS...")
    if not ingestion.start():
        logger.error("❌ Falha ao iniciar ingestão")
        sys.exit(1)
    
    logger.info(f"✅ Ingestão iniciada. Rodando por {args.duration}s...")
    logger.info("   Pressione Ctrl+C para parar antes do tempo")
    
    # Monitorar por duration segundos
    start_time = time.time()
    last_status_time = start_time
    
    while time.time() - start_time < args.duration:
        time.sleep(5)  # Check every 5 seconds
        
        # Log status a cada 60 segundos
        if time.time() - last_status_time >= 60:
            status = ingestion.get_status()
            elapsed = int(time.time() - start_time)
            remaining = args.duration - elapsed
            
            logger.info("="*80)
            logger.info(f"📊 STATUS ({elapsed}s elapsed, {remaining}s remaining)")
            logger.info(f"   Mensagens recebidas: {status['messages_received']:,}")
            logger.info(f"   Mensagens gravadas: {status['messages_written']:,}")
            logger.info(f"   Em buffer: {status['buffer_size']}")
            logger.info(f"   Total flushes: {status['total_flushes']}")
            if status['errors'] > 0:
                logger.warning(f"   ⚠️  Erros: {status['errors']}")
            logger.info("="*80)
            
            last_status_time = time.time()
    
    # Parar ingestão gracefully
    logger.info("⏰ Tempo esgotado. Parando ingestão...")
    if ingestion.stop(timeout=60):
        logger.info("✅ Ingestão parada com sucesso")
    else:
        logger.error("❌ Timeout ao parar ingestão")
        sys.exit(1)
    
    # Status final
    final_status = ingestion.get_status()
    logger.info("="*80)
    logger.info("📈 RESUMO FINAL")
    logger.info("="*80)
    logger.info(f"Mensagens recebidas: {final_status['messages_received']:,}")
    logger.info(f"Mensagens gravadas: {final_status['messages_written']:,}")
    logger.info(f"Total de flushes: {final_status['total_flushes']}")
    logger.info(f"Erros: {final_status['errors']}")
    logger.info(f"Tabela: {final_status['table']}")
    logger.info("="*80)
    logger.info("✅ Ingestão Bronze concluída com sucesso!")


if __name__ == "__main__":
    main()
