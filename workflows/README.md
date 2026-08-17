# Albion Online Market Analysis - Workflows

## 📁 Estrutura do Projeto

```
albion-tools/
├── databricks.yml              # Databricks Asset Bundle (DAB) - CI/CD config
├── workflows/
│   ├── job_definition.json     # Definição do Job em JSON (backup/referência)
│   ├── README.md               # Este arquivo
│   └── SDP/                    # Spark Declarative Pipeline
│       ├── silver/             # Silver Layer: Star Schema
│       │   ├── dim_items.py
│       │   ├── dim_locations.py
│       │   ├── dim_quality.py
│       │   ├── fact_market_orders.py
│       │   └── fact_market_history.py
│       └── gold/               # Gold Layer: Business Analytics
│           └── flipping_opportunities.py
└── app/
    └── src/scripts/
        └── bronze_ingestion.py # NATS ingestion para Bronze Layer
```

---

## 🚀 Deploy via Databricks Asset Bundles (DABs)

### **Pré-requisitos**

1. Instalar Databricks CLI:
   ```bash
   pip install databricks-cli
   ```

2. Autenticar:
   ```bash
   databricks configure --token
   # Host: https://dbc-6dd8e8ac-b9a1.cloud.databricks.com
   # Token: [seu token]
   ```

3. Verificar conexão:
   ```bash
   databricks workspace ls /Users/ztriickster@gmail.com
   ```

---

### **Deploy do Bundle**

#### **1. Ambiente de Desenvolvimento**
```bash
cd albion-tools

# Deploy (cria/atualiza recursos)
databricks bundle deploy -t dev

# Executar job manualmente
databricks bundle run orchestrator -t dev
```

#### **2. Ambiente de Produção**
```bash
# Deploy em produção
databricks bundle deploy -t prod

# Executar job
databricks bundle run orchestrator -t prod
```

#### **3. Validar Bundle (sem deploy)**
```bash
# Valida syntax e configurações
databricks bundle validate -t prod
```

---

## 🔄 Fluxo de Execução

### **Job: Albion Market Analysis - Full Orchestration**

```
Task 1: bronze_ingestion (30 min)
   │
   ├─ Conecta ao NATS (nats.albion-online-data.com)
   ├─ Consome streams:
   │    ├─ marketorders.deduped
   │    └─ markethistories.deduped
   └─ Popula tabelas Bronze:
        ├─ main.bronze.market_orders_raw
        └─ main.bronze.market_history_raw

        ↓ (depends_on)

Task 2: silver_gold_transformation (30 min)
   │
   ├─ Pipeline SDP: 054f7e79-126e-444e-9231-dc4f1a0915dc
   │
   ├─ Silver Layer (Star Schema):
   │    ├─ Dimensões:
   │    │    ├─ dim_quality
   │    │    ├─ dim_items
   │    │    └─ dim_locations
   │    └─ Fatos:
   │         ├─ fact_market_orders
   │         └─ fact_market_history
   │
   └─ Gold Layer (Analytics):
        └─ flipping_opportunities (cross-city arbitrage)
```

---

## ⏰ Agendamento

* **Frequência**: A cada 10 minutos (`0 */10 * * * ?`)
* **Timezone**: America/Sao_Paulo
* **Max Concurrent Runs**: 1 (evita overlap)
* **Timeout Global**: 30 minutos

---

## 🔧 Customizações

### **Alterar Frequência do Schedule**

Edite `databricks.yml`:

```yaml
schedule:
  quartz_cron_expression: "0 0/30 * * * ?"  # A cada 30 min
  # ou
  quartz_cron_expression: "0 0 */2 * * ?"   # A cada 2 horas
```

### **Alterar Catalogs/Schemas**

Edite as variáveis em `databricks.yml`:

```yaml
variables:
  catalog_name:
    default: main          # Mudar para outro catalog
  bronze_schema:
    default: bronze
  silver_schema:
    default: silver
```

### **Adicionar Ambiente de Staging**

```yaml
targets:
  staging:
    mode: development
    workspace:
      host: https://dbc-6dd8e8ac-b9a1.cloud.databricks.com
    variables:
      catalog_name: staging
```

Deploy:
```bash
databricks bundle deploy -t staging
```

---

## 📊 Monitoramento

### **Status do Job**
```bash
# Listar jobs
databricks jobs list --output json | jq '.jobs[] | select(.settings.name | contains("Albion"))'

# Últimas execuções
databricks jobs list-runs --job-id <JOB_ID> --limit 10

# Detalhes de uma execução
databricks jobs get-run <RUN_ID>
```

### **Pipeline SDP**
```bash
# Listar pipelines
databricks pipelines list --output json | jq '.pipelines[] | select(.name | contains("Albion"))'

# Status do pipeline
databricks pipelines get --pipeline-id 054f7e79-126e-444e-9231-dc4f1a0915dc
```

---

## 🧪 Testes Locais

### **Testar Script Bronze Ingestion**
```bash
# Simular localmente (requer NATS acessível)
python app/src/scripts/bronze_ingestion.py
```

### **Validar Python Files do SDP**
```bash
# Lint Python files
pylint workflows/SDP/**/*.py

# Format check
black --check workflows/SDP/
```

---

## 📚 Referências

* [Databricks Asset Bundles Docs](https://docs.databricks.com/dev-tools/bundles/index.html)
* [Spark Declarative Pipelines](https://docs.databricks.com/delta-live-tables/index.html)
* [Databricks Jobs API](https://docs.databricks.com/api/workspace/jobs)
* [NATS Documentation](https://docs.nats.io/)

---

## 🐛 Troubleshooting

### **Erro: "nats-py not installed"**
```yaml
# Adicionar em databricks.yml:
libraries:
  - pypi:
      package: nats-py
```

### **Erro: "Table not found: main.bronze.market_orders_raw"**
1. Executar Task 1 primeiro (bronze_ingestion)
2. Verificar se tabelas foram criadas:
   ```sql
   SHOW TABLES IN main.bronze;
   ```

### **Pipeline SDP falha: "Datasets not found"**
1. Verificar path dos arquivos Python em `workflows/SDP/`
2. Garantir que pipeline aponta para: `/Users/ztriickster@gmail.com/albion-tools/workflows/SDP`

---

## 📝 Changelog

**2026-08-17**
* Criação inicial do projeto
* Job orquestrador com 2 tasks (Bronze + Silver/Gold)
* Pipeline SDP com 6 datasets (3 dims + 2 facts + 1 analysis)
* Configuração CI/CD via Databricks Asset Bundles