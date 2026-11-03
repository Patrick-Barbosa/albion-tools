# Changelog

Mudanças relevantes deste repositório ficam neste arquivo. O formato segue o
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento segue
[SemVer](https://semver.org/lang/pt-BR/). Os canais de distribuição (branch default, tag,
`next` e skill experimental) estão em [VERSIONING.md](VERSIONING.md).

## [1.0.0] - 2026-11-03

Primeira release pública. As seis skills instalam com
`npx skills add Patrick-Barbosa/albion-tools --skill=<nome>` e rodam com Python 3.10+
padrão, sem `pip install`.

### Adicionado

**Skills**

- `albion-arbitrage-copilot` — arbitragem entre capitais e transporte de facção, com
  `scan_arbitrage.py` e `calculate_hearts.py`.
- `albion-black-market-sniper` — cruza as Buy Orders do Black Market com o menor sell
  order das capitais (`snipe_black_market.py`).
- `albion-refining-specialist` — refino com 40% de RRR na capital bônus e 53,9% com Foco,
  cascata de sobras e capacidade de carga (`calculate_refining.py`).
- `albion-build-optimizer` — menor custo por slot para um Tier Equivalente, com reroll de
  qualidade (`optimize_loadout.py`).
- `albion-market-analyst` — curva de Pareto 80/20, histórico de preço e volume e cotação
  do ouro (`analyze_pareto.py`).
- `albion-investment-wizard` — auditoria de frescor e ordem fantasma, carteira com
  alocação inteira de orçamento e simulação de encantamento (`run_wizard.py`,
  `live_market_audit.py`, `optimize_build.py`).

**Núcleo**

- `_albion_core` escrito só com a biblioteca padrão: cliente AODP com batching de 50
  itens, cache de 120s para cotações e 30min para histórico, rate limiter de 175 req/min
  e backoff em HTTP 429.
- Catálogo local com 847 itens em `data/items.json`.
- Cópia vendorizada do núcleo dentro de cada skill, gerada por `tools/sync_core.py`. O CLI
  do skills.sh copia apenas a pasta da skill, então cada uma precisa ser autocontida.
- `skills.sh.json` declarando `.opencode/skills` como container de descoberta.

**Desenvolvimento**

- 120 testes offline, sem rede, cobrindo fórmulas fiscais, catálogo, rotas de facção,
  capas, carga, anti-fantasma, rate limiter e bootstrap dos CLIs.
- `install.py` para instalação local, com `--target`, `--agents`, `--list` e `--force`.
- `VERSIONING.md` com os canais de distribuição e o fluxo de promoção de experimental.
- Licença MIT.

### Alterado

- O projeto deixou de ser um servidor MCP e passou a ser um conjunto de skills. O núcleo
  de cálculo é o mesmo; saíram `httpx`, `polars`, `nats-py`, `pydantic` e `mcp`.

### Removido

- Servidor MCP, pipeline de histórico no Databricks e integração NATS. A fonte de dados
  passou a ser apenas a API REST do AODP.

[1.0.0]: https://github.com/Patrick-Barbosa/albion-tools/releases/tag/v1.0.0
