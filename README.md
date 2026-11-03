# Albion Online Market Intelligence

[![skills.sh](https://skills.sh/b/Patrick-Barbosa/albion-tools)](https://skills.sh/Patrick-Barbosa/albion-tools)

Seis skills para o OpenCode que respondem pergunta de mercado com número: quanto sobra numa
rota Thetford → Martlock, se vale refinar T5 com Foco, qual set T7 sai mais barato. Cada
skill tem um `SKILL.md` com o fluxo de trabalho e um CLI em Python que consulta a API do
Albion Online Data Project e aplica impostos, RRR e capacidade de carga.

Os scripts usam só a biblioteca padrão do Python 3.10+. Não precisa de `pip install` nem de
venv: `python3 script.py --help` roda em máquina limpa.

## Instalação

```bash
npx skills add Patrick-Barbosa/albion-tools --skill=albion-refining-specialist
npx skills add Patrick-Barbosa/albion-tools --skill='*'
npx skills add Patrick-Barbosa/albion-tools --skill='*' -g
```

A primeira linha instala uma skill, a segunda instala as seis e a terceira instala global em
`~/.agents/skills` em vez de `.agents/skills` no projeto. O CLI grava a origem em
`skills-lock.json`, então `npx skills update` atualiza depois. Para Claude Code, Cursor ou
Codex, passe `-a <agente>`.

Cada skill leva a própria cópia de `_albion_core/` e do catálogo de itens, então
`--skill=<nome>` funciona sozinho, sem instalar mais nada.

Se preferir clonar:

```bash
git clone https://github.com/Patrick-Barbosa/albion-tools.git
cd albion-tools
python3 install.py               # instala em ~/.config/opencode/skills
python3 install.py --list        # mostra o que seria instalado
python3 install.py --target ./x  # instala em outra pasta
```

Abrir o OpenCode na raiz do repositório também funciona, porque as skills em
`skills/` são detectadas sem instalação.

## Um exemplo

Couro T4 em Martlock, com Premium e sem Foco:

```text
$ python3 skills/albion-refining-specialist/scripts/calculate_refining.py \
    --resource HIDE --tier 4 --premium

====================================================================
🏭 REFINO T4 · Martlock
====================================================================
Insumo bruto:     2x T4 Hide @ 107 🪙 (Fort Sterling)
Barra anterior:   1x T3 Leather @ 214 🪙
Produto:          Couro do Adepto vendido a 299 🪙
RRR aplicado:     40.0% (foco: não)
Custo efetivo:    265 🪙
Receita líquida:  280 🪙
Lucro por barra:  15 🪙  (ROI 5.66%)
Veredito:         🟡 Margem baixa
```

O preço de venda é o menor sell order em Martlock e o custo já desconta a taxa de 4% do
Premium. Sem `--premium` a taxa vai para 8% e o lucro cai. Os valores mudam a cada consulta
porque a fonte é o mercado ao vivo.

## As seis skills

| Skill | Para que serve | CLI |
| :--- | :--- | :--- |
| `albion-arbitrage-copilot` | Arbitragem entre capitais, transporte de facção, rotas seguras vs. Zona Vermelha, travas anti-fantasma e breakeven fiscal. | `scan_arbitrage.py`, `calculate_hearts.py` |
| `albion-black-market-sniper` | Cruza as Buy Orders do Black Market de Caerleon com o menor sell order das capitais e calcula a margem líquida. | `snipe_black_market.py` |
| `albion-refining-specialist` | Refino na capital de bônus (40% de RRR, 53,9% com Foco), cascata de sobras e kit de transporte. | `calculate_refining.py` |
| `albion-build-optimizer` | Menor custo por slot para um Tier Equivalente (4.3, 5.2, 6.1 vs 7.0) e reroll de qualidade. | `optimize_loadout.py` |
| `albion-market-analyst` | Curva de Pareto 80/20 de prata diária, histórico de preço e volume, cotação do ouro. | `analyze_pareto.py` |
| `albion-investment-wizard` | Auditoria de frescor e ordem fantasma, carteira com alocação inteira de orçamento e simulação de encantamento. | `run_wizard.py`, `live_market_audit.py`, `optimize_build.py` |

## Comandos

Os caminhos abaixo assumem a raiz do repositório. Numa skill instalada via `npx`, troque
`skills/` por `.agents/skills/`.

```bash
# Arbitragem Thetford -> Martlock, Premium, ROI mínimo de 15%, só rotas seguras
python3 skills/albion-arbitrage-copilot/scripts/scan_arbitrage.py \
  --origin Thetford --destination Martlock --premium --min-roi 15 --safe-only

# Transporte de facção: fardo de 7 corações saindo de Lymhurst
python3 skills/albion-arbitrage-copilot/scripts/calculate_hearts.py \
  --city Lymhurst --silver 1000000 --mount T5_BOAR --risk SAFE_ONLY --pack 7 --premium

# Black Market: margem mínima de 20% e cotações de até 24h
python3 skills/albion-black-market-sniper/scripts/snipe_black_market.py \
  --items T4_BAG,T5_BAG,T6_BAG --premium --min-margin 20 --max-age 86400

# Refino em cascata: 5M de orçamento em tábuas T6
python3 skills/albion-refining-specialist/scripts/calculate_refining.py \
  --resource WOOD --tier 6 --focus --premium --cascade --budget 5000000

# Carteira: 5M saindo de Lymhurst para o Black Market
python3 skills/albion-investment-wizard/scripts/run_wizard.py \
  --budget 5000000 --city Lymhurst --dest "Black Market" --premium --min-roi 15
```

Todos aceitam `--help`. Os que geram relatório aceitam `--json` para saída estruturada.

## Regras econômicas

| Regra | Valor |
| :--- | :--- |
| Setup Fee ao criar ou editar ordem | 2,5%, não reembolsável |
| Taxa de venda | 4% com Premium, 8% sem Premium |
| Venda direta em Buy Order | só a taxa de venda, sem setup fee |
| RRR de refino | 40% na capital bônus, 53,9% com Foco |
| Tier Equivalente | tier base mais encantamento (cada `.1` vale 100 IP) |
| Capacidade de carga | `(montaria + bolsa + 50) × (1 + torta%) × (1 + bota%)` |

As fórmulas completas, tabelas de tier e regras de logística estão em
[BUSINESS_RULES.md](BUSINESS_RULES.md).

## Dados e limites

A fonte é a API REST do AODP (`west`, `europe` e `asia`), que expõe `stats/prices`,
`stats/history` e `stats/gold`. O cliente em `_albion_core/http.py` usa `urllib` e faz o
mínimo para não estourar o limite: junta até 50 itens por requisição, guarda cotações por
120s e histórico por 30min, e segura o ritmo em 175 req/min (o limite oficial é 180). Em
HTTP 429 ele espera e tenta de novo.

O que você precisa saber antes de confiar num número:

- A base é alimentada por jogadores com o Albion Data Client aberto. Uma cotação pode ter
  horas de idade, e os scripts expõem `quote_age_seconds` e `freshness` para você conferir.
- Varredura de muitos itens estoura o limite da AODP. Use `--max-items` ou uma lista
  explícita.
- Sem internet não há cotação. O catálogo de itens é local, os preços não.
- O CLI calcula e mostra; ele não coloca ordem no jogo. A compra e a venda são suas.
- Refino com Foco exige Premium. Sem Premium o RRR fica em 40%.

## Versionamento

`npx skills@latest` é a versão do CLI, não da skill. A versão de uma skill é o commit ou a
tag do Git de onde ela foi copiada. Sem `#ref` o CLI usa a branch `main`; com `#v1.0.0` ele
fica congelado naquela tag.

```bash
npx skills add Patrick-Barbosa/albion-tools#v1.0.0 --skill=albion-refining-specialist
```

O histórico de versões está em [CHANGELOG.md](CHANGELOG.md) e na página de
[releases](https://github.com/Patrick-Barbosa/albion-tools/releases). Os canais, as tags e o
fluxo de promoção de experimental estão em [VERSIONING.md](VERSIONING.md).

## Contribuir

A estrutura do repositório, como rodar os testes e como alterar o núcleo compartilhado estão
em [CONTRIBUTING.md](CONTRIBUTING.md).

## Licença

MIT. Veja [LICENSE](LICENSE).
