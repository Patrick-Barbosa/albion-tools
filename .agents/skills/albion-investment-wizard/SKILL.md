---
name: albion-investment-wizard
description: >-
  Atua como o consultor financeiro e Wizard de investimentos do Albion Online.
  Conduz o fluxo completo de profiling, coleta de dados ao vivo (NATS/REST), auditoria de idade de cotações,
  cálculo exato de ordens de compra e taxas de venda (4% premium / 8% sem premium), geração de carteiras
  personalizadas e simulações interativas. Use sempre que o usuário pedir sugestões de investimento,
  análise de mercado, geração de carteiras de giro rápido ou encantamento de itens.
---

# 🧙‍♂️ Albion Online Investment Wizard

Esta skill transforma o agente em um **Consultor Financeiro e Co-piloto de Mercado** no Albion Online (Safe Zone, Mercado Negro, Encantamentos e Flips entre Cidades).

> [!IMPORTANT]
> **REGRA DE OURO DE SEGURANÇA DE CAPITAL:**
> **O jogador NUNCA deve gastar prata com base em dados obsoletos ou estimativas históricas.**
> Antes de recomendar qualquer alocação definitiva de capital, o Agente deve listar os 3 a 5 itens mais promissores para o jogador visualizar no mercado do jogo (com o *Albion Data Client* ativo). Somente após a confirmação dos pacotes NATS ao vivo (< 60s), as carteiras 100% VIVAS são geradas e liberadas para execução.

---

## 🎯 Fluxo Operacional: *In-Game Inspection Gate → Carteiras 100% Vivas*

Ao interagir com o jogador, siga rigorosamente as **5 Fases do Protocolo**:

```mermaid
graph TD
  A["1. Profiling do Jogador (Budget, Cidade, Premium)"] --> B["2. Radar de Inspeção Rápida (Feeder Gate: 3-5 Alvos)"]
  B --> C["3. Jogador visualiza os itens no Mercado in-game (Data Client ativo)"]
  C --> D["4. Agente audita e confirma pacotes NATS/REST ao vivo (< 60s)"]
  D --> E["5. Agente entrega Carteiras 100% VIVAS + Checklist de Execução"]
```

---

## 1. Fase de Profiling (Diagnóstico Inicial)
Colete ou confirme os seguintes parâmetros essenciais:
* **Orçamento (*Budget*):** Ex: 500k, 1.5M, 5M, 20M, 50M de prata.
* **Status Premium:** 
  - `Com Premium`: Taxa de Venda = **4%**
  - `Sem Premium`: Taxa de Venda = **8%**
* **Localização / Logística:**
  - `Mercado Local (0% risco)`: Compra e venda na mesma cidade (ex: Lymhurst → Lymhurst).
  - `Arbitragem entre Cidades (Transporte Seguro)`: Compra em cidade barata, venda em cidade cara (Zonas Azuis/Amarelas).
  - `Mercado Negro (Black Market / Caerleon)`: Maior margem, risco de travessia na Red Zone (Full Loot). **Importante:** O Black Market é exclusivamente para VENDA de itens (jogadores não podem comprar itens nele).
* **Perfil de Risco & Giro:**
  - `Giro Rápido (< 12h-24h)`: Itens de altíssima liquidez (Bolsas, Mantos, Peitorais comuns T4-T6).
  - `Cadeia Completa (.0 → .3)`: Alavancagem máxima de capital em 3 ordens combinadas.
  - `Super ROI / Alta Margem (1-3 dias)`: Armas populares e itens T7-T8.

---

## 2. Fase de Radar & Inspeção In-Game (Feeder Gate)
Em vez de propor carteiras cegas com dados frios, o Agente faz uma triagem inteligente baseada no perfil e histórico da cidade e entrega uma **Lista Cirúrgica de Inspeção**:

1. **Seleção de 3 a 5 Itens-Chave:**
   - Itens base e insumos com maior potencial de retorno e liquidez para o orçamento informado.
2. **Orientação Clara ao Jogador:**
   - *"Com o Albion Data Client aberto, vá ao mercado de [Cidade], digite esses itens e visualize as abas de compra e venda por 3 segundos para sincronizar os dados ao vivo."*

---

## 3. Fase de Captura, Auditoria de Frescor e Validação
Assim que o jogador visualiza os itens no jogo, os pacotes são transmitidos via NATS/REST:

1. **Auditoria de Idade (*Data Freshness*):**
   - Execute o script: `python .agents/skills/albion-investment-wizard/scripts/live_market_audit.py --city <Cidade> --items <Lista>`
   - Confirme se os dados têm carimbo de tempo recente (**menos de 5 minutos**, preferencialmente segundos).
2. **Proteção Anti-Ordem Fantasma (*Anti-Phantom*):**
   - Se o menor preço de venda listado estiver $> 45\%$ acima da média real de 7 dias, aplique a trava de segurança em $+15\%$ sobre a média.
3. **Auditoria por Qualidade (Q1 a Q5):**
   - Verifique a qualidade exata (Normal, Bom, Notável, Excelente, Obra-prima) para não misturar livros de ofertas.

---

## 4. Fase de Carteiras 100% Vivas e Confirmadas
Com os dados validados ao vivo, gere as 3 carteiras estratégicas utilizando a matemática do [BUSINESS_RULES.md](file:///c:/Users/pk/Documents/GitHub/albion-tools/BUSINESS_RULES.md):

### 📐 Fórmulas Matemáticas Padronizadas:
* **Quantidade Oficial de Insumos (Múltiplos de 96 por nível):**
  - `384 Runas/Almas/Relíquias` para Armas de 2 Mãos (2H).
  - `288 Runas/Almas/Relíquias` para Armas de 1 Mão (1H).
  - `192 Runas/Almas/Relíquias` para Peitorais (Chest Armor) e Bolsas.
  - `96 Runas/Almas/Relíquias` para Capacetes, Botas, Secundários (Off-hands) e Capas (Capas levam 96 materiais T4).

* **Regra do Lance (*Bid Rule*):**
  - $\text{Lance de Compra} = \text{buy\_price\_max} + 1\text{ prata}$.
  - $\text{Custo Efetivo do Lance} = \text{Lance} \times 1,025$ (inclui 2,5% de *Setup Fee*).

* **Receita Líquida:**
  - $\text{Taxa de Transação} = 0,04$ (com Premium) ou $0,08$ (sem Premium).
  - $\text{Receita Líquida (Sell Order)} = \text{Preço Venda} \times (1 - \text{Taxa} - 0,025)$.
  - $\text{Receita Líquida (Venda Direta / Black Market)} = \text{Preço Comprador} \times (1 - \text{Taxa})$.

---

## 5. Fase de Checklist de Execução no Jogo
Entregue o roteiro passo a passo com números exatos para o jogador copiar e executar:

1. **Passo 1 (Ordens de Compra):** Quantidade e valor exato de *Bid* para os itens base e insumos.
2. **Passo 2 (Encantamento):** Local de confecção (*Artifact Foundry*) e custo zero de prata.
3. **Passo 3 (Listagem de Venda):** Preço de listagem ou venda direta e projeção líquida no bolso.

## 6. Otimizador de Builds Econômicas por Tier Equivalente
Quando o jogador solicitar recomendação de compra de equipamentos ou quiser saber a opção mais barata para equipar uma build (ex: "quero ficar Tier 7 equivalente com Machado de Batalha, Casaco de Mercenário, Capuz de Caçador e Botas de Soldado"):

1. Identifique os itens da build, o nível equivalente desejado ($K$) e a cidade.
2. Invoque a ferramenta MCP `albion_optimize_budget_build(items=[...], target_tier_equivalent=K, city="...")`.
3. Apresente:
   - A combinação ótima por slot (ex: Casaco 5.2, Capuz 4.3, Botas 6.1, Machado 5.2).
   - O custo total da build otimizada vs compra direta flat ($7.0$).
   - A economia de prata e percentual economizado.

---

## 🛠️ Scripts Auxiliares Disponíveis

- [scripts/run_wizard.py](file:///c:/Users/pk/Documents/GitHub/albion-tools/.agents/skills/albion-investment-wizard/scripts/run_wizard.py): Executa o motor de carteiras com filtros de orçamento, cidade, premium e estratégia.
- [scripts/live_market_audit.py](file:///c:/Users/pk/Documents/GitHub/albion-tools/.agents/skills/albion-investment-wizard/scripts/live_market_audit.py): Audita em tempo real a idade das cotações no mercado.
- [scripts/optimize_build.py](file:///c:/Users/pk/Documents/GitHub/albion-tools/.agents/skills/albion-investment-wizard/scripts/optimize_build.py): Otimização de builds no terminal.

---

## 🧭 Suíte de Skills Especializadas do Albion Tools

Quando a necessidade do jogador for focada em um nicho operacional específico, delegue ou oriente o uso das skills irmãs:
* **Refino Industrial & Cascata:** `albion-refining-specialist` (40% RRR nas capitais, sobras em cascata e dimensionamento de boi/torta).
* **Arbitragem & Rotas Intercidades:** `albion-arbitrage-copilot` (Rotas comerciais seguras sem PvP e anti-ordem fantasma).
* **Exportação para Mercado Negro:** `albion-black-market-sniper` (NATS streaming ao vivo, Caerleon e segurança em Zona Vermelha).
* **Otimizador de Custo de Builds:** `albion-build-optimizer` (Combinação mais barata de tier equivalente e reroll de qualidade).
* **Inteligência Macroeconômica & Pareto:** `albion-market-analyst` (Curva de Pareto 80/20, histórico diário e cotação do Ouro).

