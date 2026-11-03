# Contribuindo

O projeto é pequeno e a maior parte do trabalho é fórmula econômica e texto de
`SKILL.md`. Antes de abrir uma mudança, rode os testes.

## Requisitos

Python 3.10 ou mais novo. Para usar as skills, nada além da biblioteca padrão. Para rodar a
suíte, `pytest`:

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest tests -v
```

`pytest.ini` já define `pythonpath = skills` e `testpaths = tests`, então os testes importam
`from _albion_core import ...` sem instalar nada.

A suíte é offline. Nenhum teste chama a AODP, então ela roda em CI e em máquina sem rede.

## Estrutura

```text
.
├── skills/
│   ├── _albion_core/          # fonte de verdade do núcleo
│   │   ├── http.py            # cliente AODP, cache e rate limit
│   │   ├── market.py          # cotações, histórico, ouro
│   │   ├── economics.py       # impostos, encantamento, arbitragem
│   │   ├── refining.py        # refino e cascata
│   │   ├── pareto.py          # curva 80/20
│   │   ├── builds.py          # tier equivalente
│   │   ├── anti_phantom.py    # breakeven, fantasma, knapsack, reroll, carga
│   │   ├── hearts.py          # transporte de facção e capas
│   │   ├── calculator.py      # fórmulas fiscais
│   │   ├── metadata.py        # catálogo PT-BR/EN
│   │   └── data/items.json    # catálogo local (847 itens)
│   └── albion-<nome>/
│       ├── SKILL.md           # fluxo de trabalho e regras de resposta
│       ├── scripts/           # CLI da skill
│       └── _albion_core/      # cópia gerada, não editar
├── tools/sync_core.py         # replica o núcleo nas skills
├── tests/                     # suíte offline
├── install.py                 # instalador local
├── skills.sh.json             # descoberta pelo CLI do skills.sh
├── opencode.json              # declara skills/ para o OpenCode
├── AGENTS.md                  # diretrizes do agente
├── BUSINESS_RULES.md          # spec de domínio
└── VERSIONING.md              # canais, tags e promoção
```

## Por que o núcleo aparece seis vezes

`npx skills add --skill=<nome>` copia apenas a pasta da skill escolhida. Se a skill
importasse `_albion_core` de fora, ela quebraria no primeiro `import` depois de instalada.
Por isso cada skill carrega a própria cópia.

As cópias são geradas. Edite só `skills/_albion_core/` e rode:

```bash
python3 tools/sync_core.py          # replica para as 6 skills
python3 tools/sync_core.py --check  # falha se alguma cópia divergir
```

O Git guarda um blob único para arquivos idênticos, então as seis cópias custam pouco no
repositório. O custo real é no working tree.

## Alterar uma fórmula

1. Edite o módulo em `skills/_albion_core/`.
2. Rode `python3 tools/sync_core.py`.
3. Rode `python3 -m pytest tests -q`. A suíte compara as cópias e falha se houver deriva.
4. Atualize `BUSINESS_RULES.md` se a regra mudou.
5. Se o resultado de um CLI mudar, acrescente um caso em `tests/`.

## Adicionar uma skill

```bash
cp -r skills/albion-refining-specialist skills/albion-minha-skill
# edite SKILL.md: name igual ao nome da pasta, description, fluxo
# troque scripts/
python3 tools/sync_core.py
python3 install.py --list           # confere a descoberta
python3 -m pytest tests -q
```

Regras:

- `name` no frontmatter tem que ser igual ao nome da pasta, em kebab-case.
- Se a skill tiver CLI, adicione um caso em `tests/test_cli.py`.
- Atualize a tabela do `README.md` e o teste `test_six_publishable_skills`.
- Skill experimental vai em `skills/.experimental/<nome>/`, com nome diferente da estável.
  O `sync_core.py` recusa nome duplicado.

## Versionamento

Tags `vX.Y.Z` na `main`. O fluxo de canais, a promoção de experimental e a depreciação
estão em [VERSIONING.md](VERSIONING.md), e o histórico em [CHANGELOG.md](CHANGELOG.md).

## Licença

Ao contribuir, você concorda que a contribuição sai sob a licença MIT deste repositório.
