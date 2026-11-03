"""Empacotamento: cada skill precisa ser autocontida para o `npx skills add`.

O CLI do skills.sh copia somente a pasta da skill escolhida. Se `_albion_core`
não estiver dentro dela, a skill instalada quebra no primeiro import.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / ".opencode" / "skills"
CORE_SOURCE = SKILLS_ROOT / "_albion_core"
CORE_NAME = "_albion_core"
STABLE_SKILL_DIRS = sorted(path.parent for path in SKILLS_ROOT.glob("*/SKILL.md"))
EXPERIMENTAL_ROOT = SKILLS_ROOT / ".experimental"
EXPERIMENTAL_SKILL_DIRS = (
    sorted(path.parent for path in EXPERIMENTAL_ROOT.glob("*/SKILL.md"))
    if EXPERIMENTAL_ROOT.is_dir()
    else []
)
SKILL_DIRS = STABLE_SKILL_DIRS + EXPERIMENTAL_SKILL_DIRS
IGNORED = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def file_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        hashes[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def test_six_publishable_skills():
    assert [skill.name for skill in STABLE_SKILL_DIRS] == [
        "albion-arbitrage-copilot",
        "albion-black-market-sniper",
        "albion-build-optimizer",
        "albion-investment-wizard",
        "albion-market-analyst",
        "albion-refining-specialist",
    ]


def test_skill_names_are_unique():
    """Estável e experimental não podem compartilhar o mesmo `name`."""
    names = [skill.name for skill in SKILL_DIRS]
    assert len(names) == len(set(names)), f"nomes duplicados: {names}"


@pytest.mark.parametrize("skill", SKILL_DIRS, ids=lambda path: path.name)
def test_frontmatter_name_matches_directory(skill: Path):
    content = (skill / "SKILL.md").read_text(encoding="utf-8")
    assert content.startswith("---\n")
    frontmatter = content.split("---", 2)[1]
    names = [line.split(":", 1)[1].strip() for line in frontmatter.splitlines() if line.startswith("name:")]
    assert names == [skill.name]


@pytest.mark.parametrize("skill", SKILL_DIRS, ids=lambda path: path.name)
def test_skill_vendors_the_shared_core(skill: Path):
    bundled = skill / CORE_NAME
    assert bundled.is_dir(), f"{skill.name} não tem {CORE_NAME}/; rode python3 tools/sync_core.py"
    assert file_hashes(bundled) == file_hashes(CORE_SOURCE), (
        f"cópia de {CORE_NAME} em {skill.name} está dessincronizada; rode python3 tools/sync_core.py"
    )


@pytest.mark.parametrize("skill", SKILL_DIRS, ids=lambda path: path.name)
def test_installed_skill_runs_standalone(skill: Path, tmp_path: Path):
    """Simula o `npx skills add`: copia só a pasta da skill para um diretório limpo."""
    installed = tmp_path / skill.name
    shutil.copytree(skill, installed, ignore=IGNORED)

    scripts = sorted((installed / "scripts").glob("*.py"))
    if not scripts:
        return  # skill puramente documental (sem CLI)

    for script in scripts:
        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=tmp_path,
        )
        assert result.returncode == 0, f"{skill.name}/{script.name}: {result.stderr}"
        assert "usage:" in result.stdout.lower()


def test_skills_manifest_points_to_the_container():
    manifest = json.loads((REPO_ROOT / "skills.sh.json").read_text(encoding="utf-8"))
    assert manifest["paths"] == ["./.opencode/skills"]
    for entry in manifest["paths"]:
        assert (REPO_ROOT / entry).is_dir()
