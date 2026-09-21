# AGENTS.md

Albion Online Market Intelligence MCP (Model Context Protocol). Servidor MCP assíncrono para conexão com agentes de IA (Antigravity, Cursor, Claude Desktop e frameworks agênticos).

## Commands

- **Run MCP Server (stdio)**: `python -m src.albion_mcp` ou `python src/albion_mcp/server.py`
- **Run MCP Server (sse)**: `python src/albion_mcp/server.py sse`
- **Tests**: `python -m pytest tests -v` — suíte de testes cobrindo rate limiter, regras fiscais, metadados PT-BR e ferramentas MCP.
- **Smoke Test ao Vivo**: `python tests/test_live_smoke.py` — verificação de conectividade com AODP REST API e detecção de arbitragem.
- **Legado**: Os dashboards anteriores (FastAPI e Streamlit) foram arquivados em `old/`.

## Architecture

- **MCP Server (`src/albion_mcp/`)**:
  - `server.py`: Instância do `MCPServer` oficial do MCP 2.x com registro de 22 ferramentas e ciclo de vida assíncrono (`server_lifespan`).
  - `core/`:
    - `rate_limiter.py`: Sliding window ativo respeitando os limites da AODP (180 req/min e 300 req/5min) com backoff automático em 429.
    - `aodp_client.py`: Cliente REST com batching de até 50 itens por chamada (respeitando limite de 4096 caracteres na URL) e cache TTL.
    - `nats_client.py`: Core streaming em tempo real via NATS Firehose (`nats://public:thenewalbiondata@nats.albion-online-data.com:4222`), buffer em memória e detecção de buy orders do Black Market com ZERO consumo de requisições HTTP.
    - `calculator.py`: Regras financeiras oficiais (4% premium / 8% sem premium, 2.5% setup fee, fórmulas de buy/sell orders e instant sell).
    - `metadata.py`: Dicionário com 12.000+ itens traduzidos em PT-BR, identificação de tiers (T2..T8), encantamentos (.0..4), slots e custos em múltiplos de 96.
    - `build_optimizer.py`: Motor de resolução de famílias de equipamentos e otimização de menor custo para builds por tier equivalente (ex: 4.3, 5.2, 6.1 vs 7.0).
    - `polars_analytics.py`: Motor analítico em Polars de alta velocidade para cálculo de refino (40% RRR / 53.9% foco), cascata de insumos, montarias e curva de Pareto.
    - `databricks_client.py`: Conector Databricks **100% opcional** via Statement Execution API. Se ausente no `.env`, o MCP opera normalmente com dados de NATS e AODP API.
  - `tools/`:
    - `items.py`: `albion_search_items`, `albion_get_item_details`.
    - `market_live.py`: `albion_get_current_prices`, `albion_nats_get_live_orders`, `albion_get_gold_prices`, `albion_get_api_quota_status`.
    - `market_history.py`: `albion_get_price_history`, `albion_get_market_pareto`.
    - `economics.py`: `albion_calculate_tax_and_fees`, `albion_simulate_enchantment`, `albion_calculate_refining`, `albion_calculate_cascade_refining`, `albion_find_arbitrage_opportunities`.
    - `build_optimizer.py`: `albion_optimize_budget_build`.
    - `anti_hallucination.py`: `albion_calculate_breakeven_price`, `albion_audit_quote_freshness_and_phantom`, `albion_allocate_portfolio_budget`, `albion_simulate_quality_reroll`, `albion_calculate_exact_loadout_capacity`, `albion_calculate_transmutation_cost`.
    - `databricks_tools.py`: `albion_databricks_status`, `albion_databricks_query_gold`.

## Ressalvas Importantes de Limites da API (AODP REST)

> [!WARNING]
> A API pública da AODP impõe limites estritos de taxa por IP:
> - **180 requisições por minuto**
> - **300 requisições a cada 5 minutos**
> 
> Boas práticas aplicadas pelo MCP:
> 1. **Batching**: O MCP concatena automaticamente dezenas de itens em um único GET (`/prices/item1,item2,item3.json`). Nunca consulte itens um a um em loops.
> 2. **Cache**: Cotações correntes têm cache TTL de 120s e histórico tem cache de 30min.
> 3. **NATS Streaming**: Para checagens frequentes ou monitoramento do Black Market, utilize sempre `albion_nats_get_live_orders`, que consome zero requisições HTTP.
> 4. **Monitoramento**: Use `albion_get_api_quota_status` para verificar a saúde da quota.

## Databricks (Opcional)

- O conector Databricks é estritamente opcional.
- Caso configurado no `.env` (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_WAREHOUSE_ID`), permite consultas na tabela Gold `main.gold.history_features`.
- Se as variáveis não estiverem configuradas, o servidor opera em modo Core sem erros.

## Suíte de Skills Antigravity (`.agents/skills/`)

O projeto opera sob uma arquitetura centrada em **Skills Especializadas**, transformando as ferramentas MCP em copilotos operacionais autônomos para cada vertente da economia do jogo:

| Skill | Slash Command | Escopo Principal | Scripts Utilitários |
| :--- | :--- | :--- | :--- |
| **`albion-investment-wizard`** | `/albion-investment-wizard` | Consultoria de investimento, profiling de capital (500k a 50M+), triagem in-game e carteiras de giro rápido (.0 -> .3). | `run_wizard.py`, `live_market_audit.py`, `optimize_build.py` |
| **`albion-refining-specialist`** | `/albion-refining-specialist` | Refino industrial nas 5 capitais bônus, RRR (40% / 53.9% foco), sobras em cascata ($1/(1-RRR)$), taxas de nutrição e montarias. | `calculate_refining.py` |
| **`albion-arbitrage-copilot`** | `/albion-arbitrage-copilot` | Rotas comerciais seguras entre cidades reais (Zonas Azuis/Amarelas), travas anti-fantasma (+45% -> +15%) e ponto de equilíbrio. | `scan_arbitrage.py` |
| **`albion-black-market-sniper`** | `/albion-black-market-sniper` | Monitoramento via NATS streaming das Buy Orders do Black Market (Caerleon), venda direta sem taxa de setup e segurança PvP. | `snipe_black_market.py` |
| **`albion-build-optimizer`** | `/albion-build-optimizer` | Resolução do menor custo por slot para atingir Tier Equivalente (ex: 4.3, 5.2, 6.1 vs 7.0) e cálculo de reroll de qualidade. | `optimize_loadout.py` |
| **`albion-market-analyst`** | `/albion-market-analyst` | Curva de Pareto 80/20, liquidez diária, histórico de vendas e monitoramento do índice do Ouro (Gold). | `analyze_pareto.py` |