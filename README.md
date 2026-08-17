# Albion Market Analysis - NATS Real-Time Ingestion

## 📋 Visão Geral

Solução de ingestão em tempo real via NATS para a camada Bronze de uma arquitetura Medallion no Databricks.

### Características

* ✅ **Ingestão em tempo real** via NATS broker público do Albion Online
* ✅ **Execução em background** (non-blocking) via threading + asyncio
* ✅ **Buffer em memória** com micro-batch writes automáticos
* ✅ **Delta Lake** como destino (ACID, time-travel, schema evolution)
* ✅ **Monitoramento** via API de status (mensagens recebidas/gravadas, erros, uptime)
* ✅ **Graceful shutdown** com flush final garantido
* ✅ **Retry logic** com backoff exponencial
* ✅ **Suporte a DABs** (Declarative Automation Bundles)

---

## 🏗️ Estrutura do Projeto

```
albion-tools/
├── databricks.yml                    # Configuração principal do Bundle
├── requirements.txt                  # Dependências Python
├── README.md                         # Esta documentação
├── resources/
│   └── bronze_nats_job.yml          # ✅ Definição do job de ingestão NATS
├── app/
│   └── src/
│       ├── nats/
│       │   ├── __init__.py
│       │   └── ingestion.py         # ✅ Módulo reutilizável NATS
│       └── scripts/
│           └── bronze_ingestion.py  # ✅ Script principal (ponto de entrada)
├── notebooks/
│   └── bronze_nats_control          # ✅ Notebook de controle interativo
└── workflows/
    └── SDP/                         # Pipelines Silver/Gold (já existentes)
```

---

## 🚀 Quickstart

### ⚡ OPÇÃO 1: Execução Rápida via Notebook (Recomendado para AGORA)

**Por que usar o notebook primeiro?**
* ✅ **Imediato**: Roda agora mesmo, sem deploy
* ✅ **Interativo**: Você vê os dados chegando em tempo real
* ✅ **Debugging fácil**: Pode parar/reiniciar instantaneamente

**Passos:**

1. **Abra o notebook** `notebooks/bronze_nats_control`

2. **Execute célula por célula**: Instalação → Configuração → Iniciar → Status → Consultar

3. **Monitorar em tempo real**:
   ```python
   status = ingestion.get_status()
   # >>> Mensagens recebidas: 42,350
   # >>> Mensagens gravadas: 41,000
   ```

**⏱️ Tempo total: ~2 minutos**

---

### 🎯 OPÇÃO 2: Deploy via DABs (Para Produção)

**Deploy:**

```bash
# 1. Validar bundle
databricks bundle validate -t dev

# 2. Deploy (cria o job no workspace)
databricks bundle deploy -t dev

# 3. Executar job manualmente
databricks bundle run bronze_nats_ingestion -t dev
```

---

## 🗃️ Schema da Tabela Bronze

| Coluna | Tipo | Nullable | Descrição |
|--------|------|----------|-----------|
| `ingestion_timestamp` | `TimestampType` | Não | Timestamp UTC da ingestão |
| `message_id` | `LongType` | Não | ID único da ordem (Albion) |
| `item_id` | `StringType` | Sim | ID do item (ex: `T4_BAG`) |
| `item_name` | `StringType` | Sim | Nome do grupo do item |
| `quality_level` | `IntegerType` | Sim | Qualidade (1-5) |
| `enchantment_level` | `IntegerType` | Sim | Encantamento (0-4) |
| `unit_price_silver` | `LongType` | Sim | Preço unitário em silver |
| `amount` | `IntegerType` | Sim | Quantidade |
| `auction_type` | `StringType` | Sim | Tipo (offer/request) |
| `expires_at` | `TimestampType` | Sim | Expiração da ordem |
| `location_id` | `IntegerType` | Sim | ID da cidade (ex: 3003 = Caerleon) |
| `raw_json` | `StringType` | Sim | Payload JSON original (debug) |

---

## 📝 Notas Técnicas

### Fonte de Dados NATS

* **Broker**: `nats://public:thenewalbiondata@nats.albion-online-data.com:4222`
* **Tópico**: `marketorders.deduped` (já deduplicado na origem)

### Conversão de Timestamps

O Albion Online usa Windows File Time (ticks desde 1601-01-01). A conversão está implementada no módulo `app/src/nats/ingestion.py`.

---

## 📜 Licença

Uso livre para fins pessoais e educacionais.
