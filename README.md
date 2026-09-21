# ⚔️ Albion Online — Market Intelligence MCP Server

Servidor **MCP (Model Context Protocol)** de alta performance projetado para conectar ferramentas agênticas de IA (Antigravity, Claude Desktop, Cursor, LangChain e agentes autônomos) ao ecossistema econômico do **Albion Online**.

O MCP opera com **Core em NATS Firehose (tempo real) e AODP REST API (batching inteligente e proteção de rate limits)**, cálculos fiscais oficiais (4% premium / 8% sem premium) e suporte analítico **100% opcional ao Databricks Unity Catalog**.

---

## 🚀 Arquitetura & Destaques

- **⚡ Core em NATS Firehose (Tempo Real)**: Escuta o broker oficial da comunidade (`nats://public:thenewalbiondata@nats.albion-online-data.com:4222`), mantendo buffer em memória para ordens do Mercado Negro (*Black Market*) e Cidades Reais com **consumo ZERO de requisições HTTP**.
- **🛡️ Proteção Rigorosa contra Limites Baixos da API AODP**:
  - Limites monitorados: **180 req/min** e **300 req/5min**.
  - **Batching automático**: Agrupa até 50 itens por chamada GET respeitando o limite de 4096 caracteres na URL.
  - **Cache em memória com TTL**: 120s para cotações correntes, 30 min para histórico diário.
  - Rate Limiter ativo (Token Bucket) e backoff automático em caso de HTTP 429.
- **🪙 Motor Econômico Oficial ([BUSINESS_RULES.md](BUSINESS_RULES.md))**:
  - Impostos: 4% com Premium, 8% sem Premium, 2.5% de Setup Fee.
  - Simulação de encantamento de itens (.0 → .1/.2/.3) respeitando múltiplos de 96 runas/almas/relíquias por slot.
  - Simulação de refino em capitais com bônus (40% RRR / 53.9% foco) e nutrição de estações.
  - Cascata de insumos e otimização de kits de transporte (Montarias, Bolsas, Tortas de Porco).
- **☁️ Databricks 100% Opcional**: Conecta à tabela Gold (`main.gold.history_features`) via Statement Execution API se configurado no `.env`; caso contrário, o MCP opera normalmente sem dependências rígidas.
- **📁 Legado Preservado**: Todo o código original de dashboards anteriores (FastAPI e Streamlit) está arquivado na pasta `old/`.

---

## 🛠️ Instalação & Execução

### 1. Instalar dependências
```bash
pip install -r requirements.txt
```

### 2. Executar o Servidor MCP

#### Modo Standard I/O (`stdio`) — Recomendado para Claude Desktop / Cursor / Antigravity:
```bash
python -m src.albion_mcp
# ou
python src/albion_mcp/server.py
```

#### Modo SSE / HTTP:
```bash
python src/albion_mcp/server.py sse
```

### 3. Rodar a Suíte de Testes
```bash
python -m pytest tests -v
```

---

## 🔌 Conectando o MCP em Agentes e Ferramentas

### No Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "albion-market": {
      "command": "python",
      "args": ["-m", "src.albion_mcp"],
      "cwd": "C:\\Users\\pk\\Documents\\GitHub\\albion-tools"
    }
  }
}
```

### No Cursor (`.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "albion-market": {
      "command": "python",
      "args": ["-m", "src.albion_mcp"]
    }
  }
}
```

---

## 📋 Catálogo de Ferramentas MCP (22 Tools)

| Categoria | Ferramenta | Descrição | Fonte Primária |
|---|---|---|---|
| **Itens & Metadados** | `albion_search_items` | Busca itens em PT-BR/EN por Tier (T4..T8), encantamento (.0..4) e categoria. | Metadados locais |
| | `albion_get_item_details` | Ficha técnica completa, slot do item e insumos de encantamento (múltiplos de 96). | Metadados locais |
| **Mercado ao Vivo** | `albion_get_current_prices` | Cotações atuais de compra e venda em lote. Aplica batching e cache TTL. | AODP REST API |
| | `albion_nats_get_live_orders` | Ordens em tempo real transmitidas pelo NATS (< 60s) com ZERO consumo de HTTP. | NATS Stream |
| | `albion_get_gold_prices` | Histórico recente de preço do ouro em prata. | AODP REST API |
| | `albion_get_api_quota_status` | Relatório de saúde do rate limiter e chamadas restantes no minuto. | Rate Limiter |
| **Histórico & Pareto** | `albion_get_price_history` | Histórico consolidado de preços e volumes diários por praça. | AODP REST API |
| | `albion_get_market_pareto` | Curva de Pareto 80/20 dos itens mais movimentados em prata diária. | Polars Engine |
| **Economia & Cálculos** | `albion_calculate_tax_and_fees` | Cálculo exato de custo efetivo, receita líquida e ROI (4% / 8% / 2.5%). | Regras Fiscais |
| | `albion_simulate_enchantment` | Simula encantamento na Artifact Foundry cruzando custo de insumos e receita líquida. | Engine Econômica |
| | `albion_calculate_refining` | Viabilidade de refino de recurso na capital com bônus (40% RRR / 53.9% Foco). | Polars Engine |
| | `albion_calculate_cascade_refining` | Simulação de refino em cascata até o tier alvo com otimização de carga e montaria. | Polars Engine |
| | `albion_find_arbitrage_opportunities` | Oportunidades de arbitragem entre Cidades Reais e para o Black Market. | Engine Econômica |
| **Builds & Equipamentos** | `albion_optimize_budget_build` | Identifica a combinação mais barata (ex: 4.3, 5.2, 6.1 vs 7.0) para Tier Equivalente alvo. | Engine de Otimização |
| **Anti-Alucinação (Zero-Error)** | `albion_calculate_breakeven_price` | Álgebra reversa exata para preço mínimo de venda e tolerância a renovações. | Engine Determinística |
| | `albion_audit_quote_freshness_and_phantom` | Auditoria estatística de idade e detecção de ordens fantasma / manipulações. | SQLite / Estatística |
| | `albion_allocate_portfolio_budget` | Knapsack inteiro de alocação de orçamento sem frações e com setup fee reservada. | Otimizador Inteiro |
| | `albion_simulate_quality_reroll` | Valor esperado (EV) e pior caso (95% confiança) para rerolls na Repair Station. | Modelo Estocástico |
| | `albion_calculate_exact_loadout_capacity` | Física exata de carga in-game com diagnóstico de sobrecarga (`SAFE_SPRINT`, etc.). | Motor de Carga |
| | `albion_calculate_transmutation_cost` | Comparativo financeiro de taxa de transmutação do sistema vs compra direta. | Transmutador Municipal |
| **Databricks (Opcional)** | `albion_databricks_status` | Verifica se o Unity Catalog está configurado no ambiente. | Databricks Client |
| | `albion_databricks_query_gold` | Consulta features pré-agregadas da tabela `main.gold.history_features`. | Databricks Client |

---

## 🧙‍♂️ Suíte de Skills Antigravity (`.agents/skills/`)

O ecossistema disponibiliza 6 Skills Especializadas com slash commands de primeira classe para agentes agênticos (Antigravity, Cursor e Claude):

| Skill | Slash Command | Descrição |
|---|---|---|
| **`albion-investment-wizard`** | `/albion-investment-wizard` | Consultoria financeira de mercado, profiling de capital (500k a 50M+), triagem in-game e carteiras vivas. |
| **`albion-refining-specialist`** | `/albion-refining-specialist` | Refino industrial nas 5 capitais bônus (40% RRR / 53.9% foco), sobras em cascata e dimensionamento de carga. |
| **`albion-arbitrage-copilot`** | `/albion-arbitrage-copilot` | Rotas de transporte seguras (Zonas Azuis/Amarelas), filtros anti-ordens fantasmas e cálculo de breakeven. |
| **`albion-black-market-sniper`** | `/albion-black-market-sniper` | Monitoramento via NATS streaming do Black Market de Caerleon, venda direta e segurança em Red Zones. |
| **`albion-build-optimizer`** | `/albion-build-optimizer` | Resolução do menor custo por slot para atingir Tier Equivalente (ex: 4.3, 5.2, 6.1 vs 7.0) e reroll de qualidade. |
| **`albion-market-analyst`** | `/albion-market-analyst` | Curva de Pareto 80/20, volume em prata diária, liquidez e monitoramento do índice do Ouro (Gold). |

---

## 📜 Aviso Legal
Ferramenta comunitária não oficial construída com dados do [Albion Online Data Project](https://www.albion-online-data.com/). Não afiliada à Sandbox Interactive GmbH.