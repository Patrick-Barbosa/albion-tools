#!/usr/bin/env python3
"""
Instalador local das skills Albion Tools.

Copia as 6 skills para o destino escolhido. Cada skill é autocontida: leva a
própria cópia de `_albion_core`, exatamente como o `npx skills add` instala.
Zero dependências — só a biblioteca padrão.

Uso:
    python3 install.py                     # instala em ~/.config/opencode/skills
    python3 install.py --target ./destino  # instala em uma pasta específica
    python3 install.py --agents            # instala em .agents/skills (Antigravity/Cursor)
    python3 install.py --list              # lista as skills disponíveis
    python3 install.py --force             # sobrescreve instalações existentes
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SOURCE = REPO_ROOT / ".opencode" / "skills"
CORE_DIR = "_albion_core"


def list_skills() -> list[str]:
    if not SOURCE.is_dir():
        return []
    return sorted(
        path.name
        for path in SOURCE.iterdir()
        if path.is_dir() and path.name != CORE_DIR and (path / "SKILL.md").is_file()
    )


def default_target() -> Path:
    return Path.home() / ".config" / "opencode" / "skills"


def copy_tree(destination: Path, force: bool) -> int:
    if not SOURCE.is_dir():
        print(f"❌ Pasta de skills não encontrada: {SOURCE}", file=sys.stderr)
        return 1

    destination.mkdir(parents=True, exist_ok=True)
    copied = 0

    for name in list_skills():
        source_item = SOURCE / name
        target_item = destination / name
        if target_item.exists() and not force:
            print(f"⏭️  {name} já existe (use --force para sobrescrever)")
            continue

        if target_item.exists():
            shutil.rmtree(target_item)

        shutil.copytree(
            source_item,
            target_item,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        copied += 1

    print(f"✅ {copied} skill(s) instalada(s) em {destination}")
    print(f"   Skills: {', '.join(list_skills())}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Instalador das skills Albion Tools")
    parser.add_argument("--target", type=Path, help="Pasta de destino")
    parser.add_argument("--agents", action="store_true", help="Instala em .agents/skills")
    parser.add_argument("--list", action="store_true", help="Lista as skills")
    parser.add_argument("--force", action="store_true", help="Sobrescreve instalações existentes")
    args = parser.parse_args()

    if args.list:
        for skill in list_skills():
            print(skill)
        return 0

    if args.target:
        destination = args.target.expanduser().resolve()
    elif args.agents:
        destination = REPO_ROOT / ".agents" / "skills"
    else:
        destination = default_target()

    return copy_tree(destination, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
