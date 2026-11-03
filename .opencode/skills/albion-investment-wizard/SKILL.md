---
name: albion-investment-wizard
description: >-
  Consultor financeiro e Wizard de investimentos do Albion Online. Conduz profiling
  do jogador, auditoria de frescor e ordens fantasmas, cálculo exato de ordens de
  compra e taxas (4% premium / 8% sem premium), carteiras com alocação inteira de
  orçamento e simulação de encantamento de itens.
---

# 🧙‍♂️ Albion Online — Investment Wizard

Transforma o agente em **Consultor Financeiro e Co-piloto de Mercado** (Safe Zone, Black Market, encantamentos e flips).

> [!IMPORTANT]
> **Regra de ouro:** nunca recomende alocar capital com base em cotação velha ou em estimativa. Rode a auditoria, mostre a idade do dado e o teto seguro de bid. Se a cotação estiver velha, mande o jogador conferir no jogo antes de comprar.

---

## 🎯 Fluxo Operacional (5 fases)

```mermaid
graph TD
  A["1. Profiling (budget, cidade, premium)"] --> B["2. Radar: 3-5 alvos"]
  B --> C["3. Jogador confere no mercado in-game"]
  C --> D["4. Auditoria de frescor e fantasma"]
  D --> E["5. Carteira com alocação inteira + checklist"]
```

### 1. Profiling
Pergunte (uma única mensagem, direta):
- **Orçamento** em prata
- **Premium** ativo? (4% vs 8%)
- **Cidade** de operação
- **Destino**: mesma cidade, outra capital ou Black Market
- **Giro**: rápido (< 24h), cadeia de encantamento (.0 → .3) ou alta margem (1–3 dias)

### 2. Radar
Liste 3–5 itens candidatos com base no orçamento e na liquidez. Peça ao jogador para abrir o mercado no jogo com o *Albion Data Client* ativo e visualizar os itens por alguns segundos — isso atualiza a AODP.

### 3. Auditoria
Rode `live_market_audit.py`. Confirme `freshness.status` e `phantom_audit.status`. Acima de 45% de desvio da média de 7 dias, aplique o teto de +15%.

### 4. Carteira
Rode o wizard: ele varre o universo, filtra por ROI, busca liquidez real e aloca o orçamento em unidades inteiras, reservando o setup fee.

### 5. Checklist
Entregue quantidades e preços exatos de bid, local de encantamento e preço de listagem.

---

## 📐 Fórmulas

* **Insumos de encantamento (múltiplos de 96):**
  - 384 para armas 2H · 288 para 1H · 192 para peitoral/bolsa · 96 para elmo/bota/secundário/capa.
* **Bid rule:** $\text{lance} = \text{buy\_price\_max} + 1$ prata; custo efetivo $= \text{lance} \times 1{,}025$.
* **Receita líquida:**
  - Sell Order: $\text{preço} \times (1 - \text{taxa} - 0{,}025)$
  - Venda direta / Black Market: $\text{preço} \times (1 - \text{taxa})$

---

## 🛠️ Comandos

> Execute os comandos **a partir da pasta desta skill** (a que contém este `SKILL.md`):
> `.opencode/skills/albion-investment-wizard/` no repositório ou `.agents/skills/albion-investment-wizard/` após `npx skills add`.

```bash
# 1. Carteira: 5M, Lymhurst -> Black Market, Premium
python3 scripts/run_wizard.py \
  --budget 5000000 --city Lymhurst --dest "Black Market" --premium --min-roi 15

# 2. Auditoria de frescor/fantasma dos alvos
python3 scripts/live_market_audit.py \
  --city Lymhurst --items T4_BAG,T5_BAG,T5_RUNE

# 3. Build econômica (T7 equivalente)
python3 scripts/optimize_build.py \
  --city Lymhurst --tier 7 --items "Machado de Guerra" "Casaco de Mercenário" "Capuz de Assassino" "Botas de Soldado"

# 4. Encantamento: custo de insumos vs venda do item encantado
python3 - <<'EOF'
import sys; sys.path.insert(0, ".")
from _albion_core import economics
print(economics.simulate_enchantment("T6_MAIN_SWORD", 1, 85000, 320, 130000, has_premium=True))
EOF

# 5. Breakeven exato
python3 - <<'EOF'
import sys; sys.path.insert(0, ".")
from _albion_core import anti_phantom
print(anti_phantom.calculate_breakeven_price(85000, is_buy_order=True, has_premium=True, target_roi_pct=15))
EOF
```

---

## 📋 Como responder ao jogador

1. Sempre declare **Premium** e a **taxa aplicada** (4% ou 8%).
2. Mostre a tabela de alocação: item, quantidade inteira, capital, lucro projetado, ROI.
3. Informe o caixa que sobrou (`cash_reserve_leftover`) — nunca aloque 100% do orçamento.
4. Sinalize itens com `phantom_audit.status != NORMAL` ou liquidez < 1/dia.
5. Feche com o checklist de execução (bid → encantamento → listagem).
