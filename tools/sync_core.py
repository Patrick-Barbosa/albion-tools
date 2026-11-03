#!/usr/bin/env python3
"""
Vendoriza o núcleo compartilhado dentro de cada skill.

O `npx skills add <owner/repo> --skill=<nome>` copia **apenas** a pasta da skill
escolhida. Para que cada skill funcione sozinha depois de instalada, ela precisa
carregar a própria cópia de `_albion_core`.

A fonte de verdade continua sendo `.opencode/skills/_albion_core/`; este script
apenas replica essa pasta para dentro das 6 skills. As cópias são versionadas
(byte a byte idênticas, então o Git guarda um único blob).

Uso:
    python3 tools/sync_core.py              # sincroniza todas as skills
    python3 tools/sync_core.py --check      # falha se alguma cópia divergir
    python3 tools/sync_core.py --skill albion-refining-specialist
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / ".opencode" / "skills"
CORE_NAME = "_albion_core"
CORE_SOURCE = SKILLS_ROOT / CORE_NAME
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def skill_dirs() -> list[Path]:
    """Skills publicáveis: pastas com SKILL.md (o núcleo fica de fora)."""
    return sorted(
        path.parent
        for path in SKILLS_ROOT.glob("*/SKILL.md")
        if path.parent.name != CORE_NAME
    )


def file_hashes(root: Path) -> dict[str, str]:
    """Mapa caminho-relativo -> sha256, ignorando artefatos de bytecode."""
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        hashes[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def sync_skill(skill: Path) -> None:
    destination = skill / CORE_NAME
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(CORE_SOURCE, destination, ignore=IGNORE)


def check_skill(skill: Path) -> list[str]:
    destination = skill / CORE_NAME
    if not destination.is_dir():
        return [f"{skill.name}: {CORE_NAME}/ ausente"]

    source_hashes = file_hashes(CORE_SOURCE)
    target_hashes = file_hashes(destination)

    problems: list[str] = []
    for name in sorted(source_hashes.keys() - target_hashes.keys()):
        problems.append(f"{skill.name}: falta {name}")
    for name in sorted(target_hashes.keys() - source_hashes.keys()):
        problems.append(f"{skill.name}: sobra {name}")
    for name in sorted(source_hashes.keys() & target_hashes.keys()):
        if source_hashes[name] != target_hashes[name]:
            problems.append(f"{skill.name}: divergente {name}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Vendoriza _albion_core nas skills")
    parser.add_argument("--check", action="store_true", help="Só verifica, sem escrever")
    parser.add_argument("--skill", action="append", dest="skills", help="Skill específica (repetível)")
    args = parser.parse_args()

    if not CORE_SOURCE.is_dir():
        print(f"❌ Núcleo não encontrado: {CORE_SOURCE}", file=sys.stderr)
        return 1

    available = {skill.name: skill for skill in skill_dirs()}
    if args.skills:
        unknown = sorted(set(args.skills) - available.keys())
        if unknown:
            print(f"❌ Skill desconhecida: {', '.join(unknown)}", file=sys.stderr)
            print(f"   Disponíveis: {', '.join(sorted(available))}", file=sys.stderr)
            return 1
        targets = [available[name] for name in args.skills]
    else:
        targets = [available[name] for name in sorted(available)]

    if args.check:
        problems = [problem for skill in targets for problem in check_skill(skill)]
        if problems:
            for problem in problems:
                print(f"❌ {problem}", file=sys.stderr)
            print("\nRode: python3 tools/sync_core.py", file=sys.stderr)
            return 1
        print(f"✅ {CORE_NAME} sincronizado em {len(targets)} skill(s)")
        return 0

    for skill in targets:
        sync_skill(skill)
        print(f"✅ {CORE_NAME} → {skill.name}/")
    print(f"\n{len(targets)} skill(s) agora são autocontidas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
