"""CLIs das skills: bootstrap de import, --help e lógica offline."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / ".opencode" / "skills"
SCRIPTS = sorted(SKILLS_DIR.glob("*/scripts/*.py"))


def test_expected_number_of_skill_scripts():
    assert len(SCRIPTS) == 9


def test_no_script_depends_on_removed_mcp_package():
    for script in SCRIPTS:
        source = script.read_text(encoding="utf-8")
        assert "src.albion_mcp" not in source, f"{script.name} ainda importa o pacote MCP removido"
        assert "import httpx" not in source, f"{script.name} ainda importa httpx"
        assert "import polars" not in source, f"{script.name} ainda importa polars"


def test_every_script_bootstraps_the_shared_core():
    for script in SCRIPTS:
        source = script.read_text(encoding="utf-8")
        assert "_albion_core" in source, f"{script.name} não importa _albion_core"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda path: path.parent.parent.name)
def test_script_help_exits_cleanly(script: Path):
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()


def test_reroll_is_fully_offline():
    script = SKILLS_DIR / "albion-build-optimizer" / "scripts" / "optimize_loadout.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--reroll",
            "--item-id",
            "T6_MAIN_SWORD",
            "--current-quality",
            "1",
            "--target-quality",
            "4",
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["item_id"] == "T6_MAIN_SWORD"
    assert payload["expected_total_cost_silver"] > 0


def test_installer_lists_six_skills():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "install.py"), "--list"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    skills = result.stdout.strip().splitlines()
    assert len(skills) == 6
    assert "albion-arbitrage-copilot" in skills
    assert "albion-investment-wizard" in skills


def test_every_skill_has_frontmatter_and_description():
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        content = skill_md.read_text(encoding="utf-8")
        assert content.startswith("---\n"), f"{skill_dir.name} sem frontmatter"
        frontmatter = content.split("---", 2)[1]
        assert f"name: {skill_dir.name}" in frontmatter
        assert "description:" in frontmatter
