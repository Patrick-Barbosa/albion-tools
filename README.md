# ⚔️ Albion Online — Market Intelligence MCP Server

Servidor **MCP (Model Context Protocol)** de alta performance projetado para conectar ferramentas agênticas de IA (**OpenCode**, Antigravity, Claude Desktop, Cursor e agentes autônomos) ao ecossistema econômico do **Albion Online**.

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

## 🤖 Guia de Instalação para OpenCode (Comando por Comando)

O [OpenCode](https://opencode.ai) possui suporte nativo ao Model Context Protocol (MCP). Siga o passo a passo exato para o seu sistema operacional:

### 🐧 Instalação no Linux (Ubuntu / Debian / Fedora / Arch)

Abra o seu terminal (Bash ou Zsh) e execute os comandos linha a linha:

#### 1. Instalar pré-requisitos do sistema (se ainda não tiver)
```bash
# Ubuntu / Debian / Pop!_OS:
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git

# Fedora:
# sudo dnf install -y python3 python3-pip git

# Arch Linux:
# sudo pacman -S python python-pip git
```

#### 2. Clonar o repositório e acessar a pasta
```bash
git clone https://github.com/Patrick-Barbosa/albion-tools.git
cd albion-tools
```

#### 3. Criar e ativar o ambiente virtual (`.venv`)
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### 4. Atualizar o pip e instalar as dependências
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 5. Executar os testes para validar a instalação
```bash
pytest tests -v
```
*(Todos os testes devem passar com sucesso).*

#### 6. Registrar o MCP no OpenCode

Você tem duas opções igualmente fáceis:

- **Opção A (Via CLI do OpenCode — Recomendada):**
  Com o `.venv` ativado na pasta do projeto, execute:
  ```bash
  opencode mcp add albion-market -- python -m src.albion_mcp
  ```

- **Opção B (Automática via `opencode.json` do projeto):**
  Este repositório já inclui o arquivo `opencode.json` pré-configurado na raiz:
  ```json
  {
    "$schema": "https://opencode.ai/config.json",
    "mcp": {
      "albion-market": {
        "type": "local",
        "command": ["python", "-m", "src.albion_mcp"],
        "enabled": true,
        "timeout": 30000
      }
    }
  }
  ```
  Basta iniciar o OpenCode a partir desta pasta (com o `.venv` ativado):
  ```bash
  opencode
  ```

#### 7. Verificar se as ferramentas foram carregadas
```bash
opencode mcp list
```
*(O `albion-market` aparecerá listado e ativo).*

---

### 🪟 Instalação no Windows (PowerShell ou Prompt de Comando)

#### Pré-requisitos no Windows:
1. **Python 3.10+**: Baixe pelo site oficial [python.org](https://www.python.org/) ou via Microsoft Store. **IMPORTANTE:** Durante a instalação, marque a caixa **"Add python.exe to PATH"**.
2. **Git**: Baixe em [git-scm.com](https://git-scm.com/).

---

#### No Windows PowerShell:

Execute os comandos abaixo no terminal do PowerShell:

#### 1. Clonar o repositório e acessar a pasta
```powershell
git clone https://github.com/Patrick-Barbosa/albion-tools.git
cd albion-tools
```

#### 2. Criar o ambiente virtual (`.venv`)
```powershell
python -m venv .venv
```

#### 3. Habilitar execução de scripts e ativar o ambiente virtual
Caso o PowerShell bloqueie a execução de scripts, libere para a sessão atual e ative:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```
*(Você verá o prefixo `(.venv)` no início da linha de comando).*

#### 4. Atualizar o pip e instalar as dependências
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### 5. Executar os testes para validar
```powershell
pytest tests -v
```

#### 6. Registrar o MCP no OpenCode

- **Opção A (Via CLI do OpenCode — Recomendada):**
  ```powershell
  opencode mcp add albion-market -- .\.venv\Scripts\python.exe -m src.albion_mcp
  ```

- **Opção B (Configuração Global no Windows):**
  Se preferir que o MCP fique acessível em qualquer pasta no OpenCode, edite `%USERPROFILE%\.config\opencode\opencode.json`:
  ```json
  {
    "$schema": "https://opencode.ai/config.json",
    "mcp": {
      "albion-market": {
        "type": "local",
        "command": ["C:\\caminho\\completo\\albion-tools\\.venv\\Scripts\\python.exe", "-m", "src.albion_mcp"],
        "cwd": "C:\\caminho\\completo\\albion-tools",
        "enabled": true,
        "timeout": 30000
      }
    }
  }
  ```

#### 7. Verificar status
```powershell
opencode mcp list
```

---

#### No Prompt de Comando (CMD Tradicional):

Se preferir o `cmd.exe`:

```cmd
:: 1. Clonar e entrar na pasta
git clone https://github.com/Patrick-Barbosa/albion-tools.git
cd albion-tools

:: 2. Criar e ativar ambiente virtual
python -m venv .venv
.venv\Scripts\activate.bat

:: 3. Instalar dependências
python -m pip install --upgrade pip
pip install -r requirements.txt

:: 4. Validar
pytest tests -v

:: 5. Conectar no OpenCode
opencode mcp add albion-market -- .venv\Scripts\python.exe -m src.albion_mcp

:: 6. Listar servidores
opencode mcp list
```

---

### 💬 Como usar no Chat do OpenCode

Após conectar o MCP, abra o chat do OpenCode e pergunte naturalmente em português ou inglês:

- *"Qual o preço atual de T4_BAG em Thetford, Caerleon e Fort Sterling?"*
- *"Simule o refino de 1000 barras de ferro T4 em Fort Sterling com e sem foco."*
- *"Encontre as melhores oportunidades de arbitragem entre Lymhurst e Caerleon."*
- *"Otimize uma build de Arco T6 equivalente gastando o mínimo de prata possível."*
- *"Mostre os itens da Curva de Pareto 80/20 em Martlock."*
- *"Verifique o status da quota da API da AODP."*

---

## 🔌 Conectando em Outros Agentes e Clientes MCP

### No Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "albion-market": {
      "command": "python",
      "args": ["-m", "src.albion_mcp"],
      "cwd": "/caminho/para/albion-tools"
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

### No Antigravity / Gemini CLI
O servidor é detectado automaticamente via `.agents/skills/` e pelas ferramentas MCP declaradas em `src/albion_mcp/server.py`.

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