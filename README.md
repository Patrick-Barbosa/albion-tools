# ⚔️ Albion Online — Market Intelligence Skills

[![skills.sh](https://skills.sh/b/Patrick-Barbosa/albion-tools)](https://skills.sh/Patrick-Barbosa/albion-tools)

Seis **skills de agente** para o [OpenCode](https://opencode.ai) que transformam o assistente em um copiloto econômico do **Albion Online**: arbitragem entre cidades, sniper do Mercado Negro, refino industrial, otimização de builds, análise macro (Pareto/ouro) e um wizard de investimentos.

> **Zero dependências.** Tudo roda com o **Python 3.10+ puro** — sem `pip install`, sem venv, sem servidor MCP, sem NATS. A única fonte de dados é a API pública do **Albion Online Data Project (AODP)**.

---

## 🚀 Instalação

### Via `npx skills` (recomendado)

```bash
# Uma skill específica
npx skills@latest add Patrick-Barbosa/albion-tools --skill=albion-refining-specialist

# Todas as 6 de uma vez
npx skills@latest add Patrick-Barbosa/albion-tools --skill='*'

# Instalação global (~/.agents/skills) em vez de .agents/skills do projeto
npx skills@latest add Patrick-Barbosa/albion-tools --skill='*' -g
```

O CLI detecta o OpenCode, copia a skill para `.agents/skills/` (projeto) ou `~/.agents/skills/` (global) e registra a origem em `skills-lock.json` — depois é só rodar `npx skills update` para atualizar. Outros agentes (Claude Code, Cursor, Codex…) funcionam com `-a <agente>`.

> [!NOTE]
> **Cada skill é autocontida.** Ela leva a própria cópia de `_albion_core/` e do catálogo de itens, então `--skill=<nome>` funciona sozinho, sem instalar nada além daquela pasta.

### Local (clone do repositório)

```bash
# 1. Clone o repositório
git clone https://github.com/Patrick-Barbosa/albion-tools.git
cd albion-tools

# 2. Instale as skills no OpenCode (global)
python3 install.py

# 3. Pronto. Abra o OpenCode e pergunte sobre o mercado.
```

### Outros destinos

```bash
python3 install.py --list                    # lista as skills disponíveis
python3 install.py --target ./minhas-skills  # pasta específica
python3 install.py --agents                  # instala em .agents/skills (Antigravity/Cursor)
python3 install.py --force                   # sobrescreve instalações existentes
```

> [!NOTE]
> Este repositório já funciona **in-place**: se você abrir o OpenCode na raiz do projeto, as skills em `.opencode/skills/` são detectadas automaticamente.

---

## 🏷️ Versionamento e canais

`npx skills@latest` é a versão do **CLI**, não da skill. A versão de uma skill é o **commit/tag do Git**:

| Canal | Comando |
| :--- | :--- |
| Estável (branch default) | `npx skills add Patrick-Barbosa/albion-tools --skill=albion-refining-specialist` |
| Pinado (tag) | `npx skills add Patrick-Barbosa/albion-tools#v1.2.0 --skill=albion-refining-specialist` |
| Experimental (branch) | `npx skills add Patrick-Barbosa/albion-tools#next --skill=albion-refining-specialist` |
| Experimental (skill separada) | `npx skills add Patrick-Barbosa/albion-tools --skill=albion-refining-specialist-next` |

`npx skills check` avisa quando há atualização e `npx skills update` atualiza seguindo o ref instalado. O fluxo completo (tags SemVer, promoção de experimental, `metadata.internal`, depreciação e lockfile) está em [`VERSIONING.md`](VERSIONING.md). O histórico de versões publicadas fica em [`CHANGELOG.md`](CHANGELOG.md) e na página de [releases](https://github.com/Patrick-Barbosa/albion-tools/releases).

> `#v1.2.0` e `#next` são exemplos de canais — substitua pelas suas tags/branches reais. O comando sem `#ref` usa a **branch default do GitHub**, então garanta que ela contém o commit publicado.

---

## 🧩 As 6 skills

| Skill | Para que serve | CLI principal |
| :--- | :--- | :--- |
| **`albion-arbitrage-copilot`** | Arbitragem entre capitais, transporte de facção (corações), rotas seguras vs. Zona Vermelha, travas anti-fantasma e breakeven fiscal. | `scan_arbitrage.py`, `calculate_hearts.py` |
| **`albion-black-market-sniper`** | Cruza Buy Orders do Black Market de Caerleon com o menor sell order das capitais e calcula a margem líquida. | `snipe_black_market.py` |
| **`albion-refining-specialist`** | Refino na capital de bônus (40% RRR / 53.9% com Foco), cascata de sobras e kit de transporte. | `calculate_refining.py` |
| **`albion-build-optimizer`** | Menor custo por slot para um Tier Equivalente (4.3, 5.2, 6.1 vs 7.0) + reroll de qualidade. | `optimize_loadout.py` |
| **`albion-market-analyst`** | Curva de Pareto 80/20 de prata diária, histórico de preço/volume e cotação do ouro. | `analyze_pareto.py` |
| **`albion-investment-wizard`** | Auditoria de frescor/fantasma, carteira com alocação inteira de orçamento e simulação de encantamento. | `run_wizard.py`, `live_market_audit.py`, `optimize_build.py` |

Cada skill tem um `SKILL.md` com o fluxo de trabalho, as fórmulas e as regras de resposta ao jogador.

---

## 💻 Exemplos de uso (CLI)

Os scripts podem ser executados diretamente — útil para testar ou automatizar. Os caminhos abaixo assumem a raiz do repositório; numa skill instalada via `npx`, troque `.opencode/skills/` por `.agents/skills/` (ou `~/.config/opencode/skills/` no modo global).

```bash
# Arbitragem: Thetford -> Martlock, Premium, ROI mínimo 15%, só rotas seguras
python3 .opencode/skills/albion-arbitrage-copilot/scripts/scan_arbitrage.py \
  --origin Thetford --destination Martlock --premium --min-roi 15 --safe-only

# Transporte de facção: fardo médio (7 corações) em Lymhurst
python3 .opencode/skills/albion-arbitrage-copilot/scripts/calculate_hearts.py \
  --city Lymhurst --silver 1000000 --mount T5_BOAR --risk SAFE_ONLY --pack 7 --premium

# Black Market: margem mínima 20% e cotações de até 24h
python3 .opencode/skills/albion-black-market-sniper/scripts/snipe_black_market.py \
  --items T4_BAG,T5_BAG,T6_BAG --premium --min-margin 20 --max-age 86400

# Refino: 1 barra T5 em Thetford com Foco (53.9% RRR)
python3 .opencode/skills/albion-refining-specialist/scripts/calculate_refining.py \
  --resource ORE --tier 5 --focus --premium

# Cascata: 5M de orçamento em tábuas T6
python3 .opencode/skills/albion-refining-specialist/scripts/calculate_refining.py \
  --resource WOOD --tier 6 --focus --premium --cascade --budget 5000000

# Build T7 equivalente em Lymhurst
python3 .opencode/skills/albion-build-optimizer/scripts/optimize_loadout.py \
  --city Lymhurst --tier 7 \
  --items "Machado de Guerra" "Casaco de Mercenário" "Capuz de Caçador" "Botas de Soldado"

# Pareto dos recursos refinados
python3 .opencode/skills/albion-market-analyst/scripts/analyze_pareto.py \
  --category "Recursos Refinados" --top 20

# Cotação do ouro
python3 .opencode/skills/albion-market-analyst/scripts/analyze_pareto.py --gold

# Carteira: 5M, Lymhurst -> Black Market
python3 .opencode/skills/albion-investment-wizard/scripts/run_wizard.py \
  --budget 5000000 --city Lymhurst --dest "Black Market" --premium --min-roi 15

# Auditoria de frescor/fantasma
python3 .opencode/skills/albion-investment-wizard/scripts/live_market_audit.py \
  --city Lymhurst --items T4_BAG,T5_BAG
```

Todos os CLIs aceitam `--help` e a maioria aceita `--json` para saída estruturada.

---

## 📐 Regras econômicas embutidas

| Regra | Valor |
| :--- | :--- |
| **Setup Fee** (criar/editar ordem) | **2,5%** não reembolsável |
| **Taxa de venda** | **4%** com Premium · **8%** sem Premium |
| **Venda direta** (Buy Order / Black Market) | Apenas a taxa de venda (sem setup fee) |
| **RRR de refino** | **40%** na capital bônus · **53,9%** com Foco |
| **Tier Equivalente** | `tier base + encantamento` (cada `.1` = +100 IP) |
| **Capacidade de carga** | `(montaria + bolsa + 50) × (1 + torta%) × (1 + bota%)` |

O detalhamento completo (fórmulas, tabelas de tiers, logística, capas de facção) está em [`BUSINESS_RULES.md`](BUSINESS_RULES.md).

---

## 🔌 Fonte de dados e limites

A AODP (`https://west.albion-online-data.com`, com variantes `europe` e `asia`) expõe:

- `stats/prices` — menor sell order e maior buy order por item/cidade/qualidade;
- `stats/history` — histórico de transações (preço médio e volume);
- `stats/gold` — cotação do ouro.

O cliente em `.opencode/skills/_albion_core/http.py` usa **somente `urllib`** e aplica:

- **batching** de até 50 itens por requisição;
- **cache TTL** de 120s para cotações e 30min para histórico/ouro;
- **rate limiter** de 175 req/min e 290 req/5min (margem sobre o limite oficial);
- **backoff** automático em HTTP 429;
- compressão `gzip/deflate` (exigida pela AODP).

> [!WARNING]
> Limites oficiais da AODP: **180 requisições por minuto** e **300 a cada 5 minutos**, por IP. Varreduras grandes devem usar `--max-items` ou listas explícitas de itens.
>
> A base é alimentada por jogadores com o *Albion Data Client* ativo. Cotações podem ter **horas de idade** — sempre confira a idade antes de comprar. Os scripts expõem `quote_age_seconds`/`freshness` para isso.

---

## 🗂️ Estrutura do repositório

```text
.
├── .opencode/skills/
│   ├── _albion_core/          # fonte de verdade do núcleo (stdlib only)
│   │   ├── http.py            # cliente AODP + cache + rate limit
│   │   ├── market.py          # cotações, histórico, ouro
│   │   ├── economics.py       # impostos, encantamento, arbitragem
│   │   ├── refining.py        # refino e cascata
│   │   ├── pareto.py          # curva 80/20
│   │   ├── builds.py          # tier equivalente
│   │   ├── anti_phantom.py    # breakeven, fantasma, knapsack, reroll, carga
│   │   ├── hearts.py          # transporte de facção e capas
│   │   ├── calculator.py      # fórmulas fiscais
│   │   ├── metadata.py        # catálogo PT-BR/EN
│   │   ├── loadout_optimizer.py
│   │   ├── faction_transport.py
│   │   ├── cape_crafting.py
│   │   └── data/items.json    # catálogo local (~847 itens)
│   ├── albion-arbitrage-copilot/
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   └── _albion_core/      # cópia vendorizada (gerada, não editar)
│   ├── albion-black-market-sniper/
│   ├── albion-build-optimizer/
│   ├── albion-investment-wizard/
│   ├── albion-market-analyst/
│   └── albion-refining-specialist/
├── tools/sync_core.py         # replica o núcleo para as 6 skills
├── skills.sh.json             # descoberta de skills pelo CLI do skills.sh
├── tests/                     # suíte offline (sem rede)
├── install.py                 # instalador local alternativo
├── AGENTS.md                  # diretrizes do agente
├── VERSIONING.md              # canais, tags e promoção de experimental
├── BUSINESS_RULES.md          # spec de domínio
└── opencode.json
```

---

## 🧪 Testes

A suíte é **100% offline** (nenhuma chamada de rede) e cobre fórmulas fiscais, catálogo, rotas de facção, capas, carga, anti-fantasma, rate limiter e o bootstrap dos CLIs.

```bash
# requer apenas pytest
python3 -m pytest tests -v
```

`pytest.ini` já configura `pythonpath = .opencode/skills`, então os testes importam `from _albion_core import ...` sem instalação.

> [!IMPORTANT]
> Ao alterar qualquer módulo de `.opencode/skills/_albion_core/`, rode `python3 tools/sync_core.py` para replicar a mudança nas 6 skills. A suíte falha se alguma cópia vendorizada divergir.

---

## ❓ Perguntas frequentes

**Preciso de Premium para usar as skills?**
Não. As skills funcionam com ou sem Premium — mas a taxa muda (4% vs 8%) e o refino com Foco exige Premium. Sempre informe seu status.

**As skills funcionam em qualquer região?**
Sim: `--region americas` (padrão), `europe` ou `asia`.

**Como atualizo as skills?**
Instaladas via `npx`: rode `npx skills update` (ou repita o `npx skills add`). Instalações locais: `git pull && python3 install.py --force`.

**Por que a cotação está velha?**
A AODP depende de jogadores com o *Albion Data Client*. Abra o mercado no jogo com o client ativo para atualizar os dados. Os scripts mostram a idade da cotação e classificam o risco.

**O que aconteceu com o servidor MCP?**
Foi removido na migração para skills-only. O núcleo de cálculo é o mesmo, agora sem `httpx`, `polars`, `nats-py`, `pydantic` ou `mcp`.

---

## 📄 Licença

Distribuído sob a licença **MIT**. Veja [LICENSE](LICENSE) para o texto completo.

Você pode usar, copiar, modificar e redistribuir as skills livremente, inclusive comercialmente, desde que preserve o aviso de copyright.
