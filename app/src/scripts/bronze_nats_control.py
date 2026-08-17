#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bronze NATS Control Script
==========================

Script de controle para ingestão em tempo real via NATS.
Pode ser executado diretamente ou importado como módulo.

Uso:
    # Modo interativo (requer notebook/shell)
    python bronze_nats_control.py
    
    # Ou via importação
    from bronze_nats_control import start_ingestion, stop_ingestion
"""

import os
from pathlib import Path

# Adicionar diretório pai ao path de forma segura (compatível com Databricks / exec)
try:
    _current_dir = Path(__file__).resolve().parent
except NameError:
    _current_dir = Path.cwd()

for _p in [
    str(_current_dir.parent),                  # app/src
    str(_current_dir.parent.parent),           # app
    str(_current_dir),                         # app/src/scripts
    str(Path.cwd()),                           # workspace root
    str(Path.cwd() / "app" / "src"),           # workspace/app/src
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from nats.ingestion import NATSBronzeIngestion
except ImportError:
    from app.src.nats.ingestion import NATSBronzeIngestion

# ============================================================================
# ⚙️ CONFIGURAÇÃO
# ============================================================================

CONFIG = {
    # Unity Catalog
    "catalog": "main",
    "schema": "albion",
    "table": "market_orders_bronze",
    
    # NATS Connection
    "nats_url": "nats://public:thenewalbiondata@nats.albion-online-data.com:4222",
    "nats_subject": "marketorders.deduped",
    
    # Performance
    "buffer_size": 1000,
    "flush_interval_seconds": 30,
    "max_retries": 3,
}

# Instância global para controle
_ingestion_instance = None


# ============================================================================
# 🚀 FUNÇÕES DE CONTROLE
# ============================================================================

def start_ingestion(config=None):
    """
    Inicia a ingestão em background.
    
    Args:
        config (dict, optional): Configuração customizada. 
                                 Se None, usa CONFIG padrão.
    
    Returns:
        NATSBronzeIngestion: Instância da ingestão iniciada.
    """
    global _ingestion_instance
    
    if _ingestion_instance is not None and _ingestion_instance.is_running():
        print("⚠️  Ingestão já está rodando!")
        return _ingestion_instance
    
    cfg = config or CONFIG
    
    print("🚀 Iniciando ingestão NATS...")
    print(f"   Destino: {cfg['catalog']}.{cfg['schema']}.{cfg['table']}")
    print(f"   Buffer: {cfg['buffer_size']} msgs")
    print(f"   Flush: {cfg['flush_interval_seconds']}s")
    print()
    
    _ingestion_instance = NATSBronzeIngestion(
        catalog_name=cfg["catalog"],
        schema_name=cfg["schema"],
        table_name=cfg["table"],
        nats_url=cfg["nats_url"],
        nats_subject=cfg["nats_subject"],
        buffer_size=cfg["buffer_size"],
        flush_interval_seconds=cfg["flush_interval_seconds"],
        max_retries=cfg["max_retries"],
    )
    
    _ingestion_instance.start()
    print("✅ Ingestão iniciada em background!\n")
    
    return _ingestion_instance


def get_status():
    """
    Obtém o status atual da ingestão.
    
    Returns:
        dict: Status da ingestão ou None se não estiver rodando.
    """
    global _ingestion_instance
    
    if _ingestion_instance is None:
        print("❌ Ingestão não foi inicializada.")
        print("   Execute: start_ingestion()")
        return None
    
    status = _ingestion_instance.get_status()
    
    # Formatar saída
    print("📊 STATUS DA INGESTÃO")
    print("=" * 60)
    
    state_emoji = "✅" if status["state"] == "running" else "⏸️"
    print(f"{state_emoji} Estado: {status['state'].upper()}")
    print(f"📨 Mensagens recebidas: {status['messages_received']:,}")
    print(f"💾 Mensagens gravadas: {status['messages_written']:,}")
    print(f"📦 Em buffer: {status['buffer_size']}")
    
    if status.get("errors"):
        print(f"❌ Erros: {len(status['errors'])}")
        for err in status["errors"][-3:]:  # Últimos 3 erros
            print(f"   - {err}")
    
    print(f"⏱️  Uptime: {status['uptime_seconds']:.0f}s ({status['uptime_seconds']/60:.1f}min)")
    
    if status["last_flush_seconds_ago"] is not None:
        print(f"🔄 Último flush: {status['last_flush_seconds_ago']:.1f}s atrás")
    
    print("=" * 60)
    
    return status


def stop_ingestion(timeout=60):
    """
    Para a ingestão gracefully.
    
    Args:
        timeout (int): Tempo máximo de espera em segundos.
    
    Returns:
        bool: True se parou com sucesso, False caso contrário.
    """
    global _ingestion_instance
    
    if _ingestion_instance is None:
        print("ℹ️  Nenhuma ingestão ativa para parar.")
        return True
    
    if not _ingestion_instance.is_running():
        print("ℹ️  Ingestão já está parada.")
        return True
    
    print(f"🛑 Parando ingestão (timeout: {timeout}s)...")
    success = _ingestion_instance.stop(timeout=timeout)
    
    if success:
        print("✅ Ingestão parada com sucesso!")
        print("   Todos os dados em buffer foram gravados.")
        _ingestion_instance = None
    else:
        print("❌ Timeout ao parar ingestão.")
        print("   Tente aumentar o timeout ou reinicie o cluster.")
    
    return success


def query_latest_data(limit=20):
    """
    Consulta os últimos registros ingeridos.
    
    Args:
        limit (int): Número de registros a retornar.
    
    Returns:
        DataFrame: Últimos registros ou None se houver erro.
    """
    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.getOrCreate()
        
        cfg = CONFIG
        table_name = f"{cfg['catalog']}.{cfg['schema']}.{cfg['table']}"
        
        print(f"🔍 Consultando últimos {limit} registros de {table_name}...\n")
        
        df = spark.sql(f"""
            SELECT 
                ingestion_timestamp,
                item_name,
                quality_level,
                enchantment_level,
                unit_price_silver,
                amount,
                location_id
            FROM {table_name}
            ORDER BY ingestion_timestamp DESC
            LIMIT {limit}
        """)
        
        df.show(truncate=False)
        return df
        
    except Exception as e:
        print(f"❌ Erro ao consultar dados: {e}")
        return None


def get_stats():
    """
    Obtém estatísticas gerais da tabela Bronze.
    
    Returns:
        DataFrame: Estatísticas ou None se houver erro.
    """
    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.getOrCreate()
        
        cfg = CONFIG
        table_name = f"{cfg['catalog']}.{cfg['schema']}.{cfg['table']}"
        
        print(f"📈 Estatísticas de {table_name}...\n")
        
        df = spark.sql(f"""
            SELECT 
                COUNT(*) as total_registros,
                COUNT(DISTINCT item_name) as itens_unicos,
                COUNT(DISTINCT location_id) as cidades,
                MIN(ingestion_timestamp) as primeira_ingestao,
                MAX(ingestion_timestamp) as ultima_ingestao
            FROM {table_name}
        """)
        
        df.show(truncate=False)
        return df
        
    except Exception as e:
        print(f"❌ Erro ao obter estatísticas: {e}")
        return None


# ============================================================================
# 🎛️ MENU INTERATIVO
# ============================================================================

def interactive_menu():
    """
    Menu interativo para controle da ingestão.
    """
    print("\n" + "="*60)
    print("🎮 BRONZE NATS CONTROL - MENU INTERATIVO")
    print("="*60)
    print()
    print("1. 🚀 Iniciar Ingestão")
    print("2. 📊 Ver Status")
    print("3. 🔍 Consultar Últimos Dados")
    print("4. 📈 Ver Estatísticas")
    print("5. 🛑 Parar Ingestão")
    print("6. ❌ Sair")
    print()
    
    while True:
        try:
            choice = input("Escolha uma opção (1-6): ").strip()
            
            if choice == "1":
                start_ingestion()
            elif choice == "2":
                get_status()
            elif choice == "3":
                query_latest_data()
            elif choice == "4":
                get_stats()
            elif choice == "5":
                stop_ingestion()
            elif choice == "6":
                print("\n👋 Encerrando...")
                if _ingestion_instance and _ingestion_instance.is_running():
                    print("⚠️  Parando ingestão antes de sair...")
                    stop_ingestion()
                break
            else:
                print("❌ Opção inválida. Tente novamente.")
            
            print()
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrompido pelo usuário.")
            if _ingestion_instance and _ingestion_instance.is_running():
                print("Parando ingestão...")
                stop_ingestion()
            break
        except Exception as e:
            print(f"❌ Erro: {e}")


# ============================================================================
# 🎯 MAIN
# ============================================================================

if __name__ == "__main__":
    # Se executado diretamente, mostra menu interativo
    interactive_menu()
