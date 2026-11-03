# 🏷️ Versionamento e Gestão das Skills

Como este repositório é publicado via `npx skills add`, o versionamento segue o **Git**, não o npm. Esta página explica os canais (estável, pinado, experimental), como promover uma mudança e como os usuários atualizam.

---

## 1. `@latest` é o CLI, não a skill

```bash
npx skills@latest add Patrick-Barbosa/albion-tools --skill=albion-refining-specialist
#          ^^^^^^^ versão do pacote npm "skills" (o CLI)
```

- `skills@latest` → última versão **do CLI** publicada no npm. Para reprodutibilidade, fixe: `npx skills@1.7.6`.
- A skill **não tem campo `version`** no padrão Agent Skills. A versão real de uma skill é o **commit/tag do Git** de onde ela foi copiada.
- Sem `#ref`, o CLI usa a **branch default** do repositório no GitHub. É o "latest" da skill.
- O `skills-lock.json` grava `ref`, `skillPath` e `skillFolderHash`; é isso que `npx skills check` e `npx skills update` usam.

> [!IMPORTANT]
> Não existe `skill@latest` nem `skill@1.2.0`. O `@` depois do repo é **filtro de skill** (`owner/repo@nome-da-skill`). Versão é sempre `#ref` (branch ou tag).

---

## 2. Canais

| Canal | Comando | O que segue |
| :--- | :--- | :--- |
| **Estável** | `npx skills add owner/repo --skill=X` | HEAD da branch default |
| **Pinado** | `npx skills add owner/repo#v1.2.0 --skill=X` | Tag imutável |
| **Experimental (branch)** | `npx skills add owner/repo#next --skill=X` | HEAD da branch `next` |
| **Experimental (skill)** | `npx skills add owner/repo --skill=X-next` | Skill separada, mesmo branch |
| **Oculta/internal** | `--skill=X` (nome explícito) | `metadata.internal: true` some do `--list` |

Sintaxe combinada: `owner/repo#ref@skill`

```bash
npx skills add Patrick-Barbosa/albion-tools#next@albion-refining-specialist
```

---

## 3. Release estável (branch default)

```bash
# 1. Tudo verde
python3 tools/sync_core.py --check
python3 -m pytest tests -q

# 2. Tag anotada (SemVer)
git tag -a v1.2.0 -m "albion-tools 1.2.0"
git push origin <branch-default> --tags
```

- **MAJOR** (`v2.0.0`): quebra de contrato — flags de CLI renomeadas/removidas, mudança de formato do `--json`, regra econômica que altera resultados.
- **MINOR** (`v1.3.0`): nova skill, novo flag, novo relatório.
- **PATCH** (`v1.2.1`): correção de fórmula, ajuste de texto, atualização do catálogo.

Quem instalou sem `#ref` continua na branch default e recebe a próxima release com `npx skills update`. Quem instalou com `#v1.2.0` fica congelado até reinstalar com outra tag.

> [!WARNING]
> O comando sem `#ref` usa a **branch default do GitHub**, não a branch local em que você está. Garanta que o commit/tag publicado está na default (ou passe o `#ref` explicitamente).

---

## 4. Experimental

### Opção A — branch `next` (recomendado para mudanças grandes)

```bash
git checkout -b next
# ... mudanças breaking ...
git push -u origin next

# testar como usuário
npx skills add Patrick-Barbosa/albion-tools#next --skill=albion-refining-specialist
```

- Usuários estáveis não são afetados.
- `npx skills check` / `update` seguem a branch `next` para quem instalou com `#next`.
- Promoção: `git checkout <default> && git merge next && git tag v2.0.0`.
- Quem estava em `#next` deve reinstalar sem o `#next` (ou com a tag) para migrar ao estável.

### Opção B — skill experimental no mesmo branch

```text
.opencode/skills/
├── albion-refining-specialist/          # estável
└── .experimental/
    └── albion-refining-specialist-next/ # experimental
        ├── SKILL.md                     # name: albion-refining-specialist-next
        └── scripts/
```

- O CLI varre o container `./.opencode/skills` até 3 níveis, então a pasta `.experimental/` é descoberta sem config extra.
- **Use um nome diferente** (`-next`, `-beta`). O CLI mantém o primeiro `name` encontrado e a ordem de varredura não é garantida — nome repetido gera comportamento imprevisível.
- Rode `python3 tools/sync_core.py` para vendorizar o núcleo na skill experimental também (o script já inclui `.experimental/`).
- `python3 install.py` instala **apenas as estáveis**; a experimental é instalada via `npx ... --skill=albion-refining-specialist-next`.

### Opção C — esconder do `--list` com `metadata.internal`

```yaml
---
name: albion-refining-specialist-next
description: Versão experimental do especialista em refino.
metadata:
  internal: true
---
```

- Some do `--list` e da instalação "todas".
- Continua instalável **pelo nome explícito**: `--skill=albion-refining-specialist-next`.
- `INSTALL_INTERNAL_SKILLS=1` revela a skill no `--list`.
- Use para WIP que ainda não deve ser descoberto — não como substituto de canal.

### Promoção de uma experimental (Opção B/C)

```bash
git mv .opencode/skills/.experimental/albion-refining-specialist-next \
       .opencode/skills/albion-refining-specialist
# editar name: no SKILL.md, remover metadata.internal
python3 tools/sync_core.py
python3 -m pytest tests -q
git tag -a v1.3.0 -m "promove refino v2"
```

Atualize a tabela do `README.md` e a lista de `tests/test_skill_bundles.py` (`test_six_publishable_skills`).

---

## 5. Versão visível no `SKILL.md` (opcional)

O padrão Agent Skills permite `metadata` (mapa string→string). O CLI **não usa** esse campo para atualizar, mas ele documenta a versão para humanos e para o agente:

```yaml
metadata:
  version: "1.2.0"
  channel: stable
```

Regra: a **tag Git é a fonte de verdade**; o `metadata.version` é espelho. Se adotar, atualize os dois no mesmo commit de release.

---

## 6. Lockfile, update e CI

| Arquivo | Escopo | Versionar? |
| :--- | :--- | :--- |
| `skills-lock.json` | Projeto (`.agents/`) | **Sim**, commit no projeto que usa as skills |
| `~/.agents/.skill-lock.json` | Global | Não |

```bash
npx skills list                 # o que está instalado
npx skills check                # há atualização? (exit 1 se sim)
npx skills update [skill]       # atualiza seguindo o ref gravado
npx skills remove <skill>       # desinstala
```

- `check` compara o `skillFolderHash` com o conteúdo atual da origem (GitHub Trees API).
- `update` refaz o fetch do `ref` gravado: branch avança, tag fica parada.
- `check` com exit 1 é um bom gate de CI num repositório que consome as skills.

---

## 7. Depreciar ou remover uma skill

1. **Aviso**: mantenha a skill por uma release com a descrição iniciando `[DEPRECIADA]` e o `SKILL.md` apontando para a substituta.
2. **Remoção**: apague a pasta, rode `tools/sync_core.py`, `pytest` e tagueie um MAJOR.
3. `npx skills check` avisa os usuários que a skill sumiu da origem e oferece removê-la; `npx skills remove <nome>` remove na mão.

---

## 8. Checklist para criar uma skill nova

```bash
cp -r .opencode/skills/albion-refining-specialist .opencode/skills/albion-minha-skill
# editar SKILL.md: name = nome da pasta, description, fluxo
# editar/trocar scripts/
python3 tools/sync_core.py          # vendoriza _albion_core
python3 install.py --list           # confere a descoberta
python3 -m pytest tests -q          # empacotamento + CLIs
```

- `name` deve ser igual ao nome da pasta (lowercase, hífens).
- Atualize a tabela do `README.md` e `test_six_publishable_skills`.
- Se a skill tiver CLI, adicione um caso em `tests/test_cli.py` (contagem de scripts).

---

## 9. Mudanças no núcleo compartilhado

- Edite **somente** `.opencode/skills/_albion_core/`.
- Rode `python3 tools/sync_core.py` e commite as 6 cópias junto.
- `tools/sync_core.py --check` e `tests/test_skill_bundles.py` falham se alguma cópia divergir.
- Uma mudança breaking no núcleo deve ir para a branch `next` e virar MAJOR na promoção.
