"""Manifestos de plugin: Claude Code, Codex e GitHub Copilot.

Os quatro clientes leem arquivos diferentes, mas todos apontam para a raiz do
repositório, onde ficam `plugin.json` e `skills/`. Este teste impede que um
manifesto aponte para o lugar errado ou que as versões divirjam.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "skills"
STABLE_SKILL_DIRS = sorted(path.parent for path in SKILLS_ROOT.glob("*/SKILL.md"))
PLUGIN_NAME = "albion-tools"

AGENT_PLUGINS_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
AGENT_PLUGINS_FIELDS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}
PLUGIN_NAME_PATTERN = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")


def load(relative: str) -> dict:
    return json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))


def test_agent_plugins_manifest_is_closed_and_valid():
    manifest = load("plugin.json")
    assert manifest["$schema"] == AGENT_PLUGINS_SCHEMA
    assert set(manifest) <= AGENT_PLUGINS_FIELDS
    assert manifest["name"] == PLUGIN_NAME
    assert len(manifest["name"]) <= 64
    assert PLUGIN_NAME_PATTERN.fullmatch(manifest["name"])
    # Agent Plugins 1.0 descobre skills em skills/, então o campo `skills`
    # não existe e não pode ser usado para apontar para outro diretório.
    assert "skills" not in manifest


def test_claude_plugin_lists_every_stable_skill():
    manifest = load(".claude-plugin/plugin.json")
    assert manifest["name"] == PLUGIN_NAME
    declared = [Path(path).as_posix() for path in manifest["skills"]]
    expected = [skill.relative_to(REPO_ROOT).as_posix() for skill in STABLE_SKILL_DIRS]
    assert declared == expected
    for path in declared:
        assert (REPO_ROOT / path / "SKILL.md").is_file()


def test_versions_agree_everywhere():
    versions = {
        "plugin.json": load("plugin.json")["version"],
        ".claude-plugin/plugin.json": load(".claude-plugin/plugin.json")["version"],
        ".github/plugin/marketplace.json": load(".github/plugin/marketplace.json")["metadata"]["version"],
    }
    assert len(set(versions.values())) == 1, versions
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{versions['plugin.json']}]" in changelog


def test_claude_marketplace_points_to_repository_root():
    manifest = load(".claude-plugin/marketplace.json")
    assert manifest["name"] == PLUGIN_NAME
    assert manifest["owner"]["name"]
    assert len(manifest["plugins"]) == 1
    entry = manifest["plugins"][0]
    assert entry["name"] == PLUGIN_NAME
    assert entry["source"] == "./"
    assert (REPO_ROOT / ".claude-plugin" / "plugin.json").is_file()


def test_codex_marketplace_has_required_policy():
    manifest = load(".agents/plugins/marketplace.json")
    assert manifest["name"] == PLUGIN_NAME
    assert manifest["interface"]["displayName"]
    assert len(manifest["plugins"]) == 1
    entry = manifest["plugins"][0]
    assert entry["name"] == PLUGIN_NAME
    assert entry["source"] == {"source": "local", "path": "./"}
    assert entry["source"]["path"].startswith("./")
    assert ".." not in entry["source"]["path"]
    assert set(entry["policy"]) == {"installation", "authentication"}
    assert entry["policy"]["installation"] in {"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"}
    assert entry["policy"]["authentication"] in {"ON_INSTALL", "ON_USE"}
    assert entry["category"]


def test_copilot_marketplace_points_to_repository_root():
    manifest = load(".github/plugin/marketplace.json")
    assert manifest["name"] == PLUGIN_NAME
    assert manifest["owner"]["name"]
    assert len(manifest["plugins"]) == 1
    entry = manifest["plugins"][0]
    assert entry["name"] == PLUGIN_NAME
    assert entry["source"] == "./"
    assert entry["version"] == manifest["metadata"]["version"]
    assert (REPO_ROOT / "plugin.json").is_file()
