import json
import sys
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch

import mmcp.presentation.cli.cli as cli
from mmcp.infrastructure.installation.context_life_installer import (
    copy_skill_to_antigravity,
    copy_skill_to_opencode,
    get_skill_source_dir,
    install_context_life,
    install_skill_for_target,
    verify_install,
)


# ---------------------------------------------------------------------------
# Skill source fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bundled_skill(tmp_path: Path) -> Path:
    """Create a fake bundled skill source tree in a separate location from the test destination.

    Source goes to tmp_path/skill-source/ so it doesn't collide with destinations.
    """
    source_root = tmp_path / "skill-source" / "context-life-integration"
    source_root.mkdir(parents=True)
    (source_root / "SKILL.md").write_text("# Skill\nHello world.", encoding="utf-8")
    (source_root / "README.md").write_text("Readme content.", encoding="utf-8")
    return source_root


@pytest.fixture
def installer_with_skill(tmp_path: Path, monkeypatch: MonkeyPatch, bundled_skill: Path) -> Path:
    """Patch get_skill_source_dir to return our fake bundled skill directory."""
    import mmcp.infrastructure.installation.context_life_installer as installer_module

    monkeypatch.setattr(installer_module, "get_skill_source_dir", lambda: bundled_skill)
    return tmp_path


# ---------------------------------------------------------------------------
# Phase 1 — Skill source resolution (bundled)
# ---------------------------------------------------------------------------

def test_get_skill_source_dir_returns_valid_path():
    """get_skill_source_dir returns a path where SKILL.md exists (real bundled skill)."""
    path = get_skill_source_dir()
    assert path.exists()
    assert (path / "SKILL.md").exists()


def test_get_skill_source_dir_raises_when_bundled_missing(monkeypatch: MonkeyPatch):
    """get_skill_source_dir raises FileNotFoundError when bundled skill is missing."""
    import importlib.resources

    def fake_files(*args, **kwargs):
        raise FileNotFoundError("Bundled skill not found in package")

    monkeypatch.setattr(importlib.resources, "files", fake_files)

    with pytest.raises(FileNotFoundError) as exc_info:
        get_skill_source_dir()
    assert "Bundled skill" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Phase 2 — Skill copy implementation
# ---------------------------------------------------------------------------

def test_copy_skill_to_opencode(installer_with_skill: Path, bundled_skill: Path, tmp_path: Path):
    copy_skill_to_opencode(tmp_path)

    dest = tmp_path / ".config" / "opencode" / "skills" / "context-life-integration"
    assert dest.exists()
    assert (dest / "SKILL.md").exists()
    assert (dest / "README.md").exists()


def test_copy_skill_to_opencode_overwrites_existing(installer_with_skill: Path, bundled_skill: Path, tmp_path: Path, caplog):
    import logging
    caplog.set_level(logging.INFO)

    dest = tmp_path / ".config" / "opencode" / "skills" / "context-life-integration"
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("old", encoding="utf-8")

    copy_skill_to_opencode(tmp_path)

    assert (dest / "SKILL.md").read_text(encoding="utf-8") == "# Skill\nHello world."
    assert any("already present" in record.message for record in caplog.records)


def test_copy_skill_to_antigravity_creates_parent_dirs(installer_with_skill: Path, bundled_skill: Path, tmp_path: Path):
    assert not (tmp_path / ".gemini").exists()
    copy_skill_to_antigravity(tmp_path)

    dest = tmp_path / ".gemini" / "skills" / "context-life-integration"
    assert dest.exists()
    assert (dest / "SKILL.md").exists()


def test_copy_skill_skips_existing(installer_with_skill: Path, bundled_skill: Path, tmp_path: Path):
    dest = tmp_path / ".gemini" / "skills" / "context-life-integration"
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("old", encoding="utf-8")

    copy_skill_to_antigravity(tmp_path)

    # Overwrites without error (dirs_exist_ok=True)
    assert (dest / "SKILL.md").read_text(encoding="utf-8") == "# Skill\nHello world."


def test_install_skill_for_target_dispatches_opencode(installer_with_skill: Path, bundled_skill: Path, tmp_path: Path):
    install_skill_for_target("opencode", tmp_path)
    assert (tmp_path / ".config" / "opencode" / "skills" / "context-life-integration").exists()


def test_install_skill_for_target_dispatches_antigravity(installer_with_skill: Path, bundled_skill: Path, tmp_path: Path):
    install_skill_for_target("antigravity", tmp_path)
    assert (tmp_path / ".gemini" / "skills" / "context-life-integration").exists()


def test_install_skill_for_target_vscode_silent_noop(installer_with_skill: Path, bundled_skill: Path, tmp_path: Path):
    # Should not raise — VS Code has no skill system
    install_skill_for_target("vscode", tmp_path)


def test_install_skill_for_target_unknown_raises(installer_with_skill: Path, bundled_skill: Path, tmp_path: Path):
    with pytest.raises(ValueError, match="Unknown installation target"):
        install_skill_for_target("unknown", tmp_path)


# ---------------------------------------------------------------------------
# Phase 3 — Verification
# ---------------------------------------------------------------------------

def test_verify_install_returns_true_when_skill_present(
    installer_with_skill: Path, bundled_skill: Path, tmp_path: Path
):
    # OpenCode: MCP config + skill present
    cfg_path = tmp_path / ".config" / "opencode" / "opencode.json"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text('{"mcp": {"context-life": {}}}', encoding="utf-8")
    copy_skill_to_opencode(tmp_path)

    mcp_ok, skill_ok, msg = verify_install("opencode", tmp_path)
    assert mcp_ok is True
    assert skill_ok is True
    assert "MCP and skill installed" in msg


def test_verify_install_returns_false_when_skill_missing(
    installer_with_skill: Path, bundled_skill: Path, tmp_path: Path
):
    cfg_path = tmp_path / ".config" / "opencode" / "opencode.json"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text('{"mcp": {"context-life": {}}}', encoding="utf-8")

    mcp_ok, skill_ok, msg = verify_install("opencode", tmp_path)
    assert mcp_ok is True
    assert skill_ok is False
    assert "skill missing" in msg


def test_verify_install_vscode_no_skill_check(
    installer_with_skill: Path, bundled_skill: Path, monkeypatch: MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    cfg_path = tmp_path / "AppData" / "Roaming" / "Code" / "User" / "mcp.json"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text('{"servers": {"context-life": {}}}', encoding="utf-8")

    mcp_ok, skill_ok, msg = verify_install("vscode", tmp_path)
    assert mcp_ok is True
    assert skill_ok is True  # VS Code always returns True for skill_ok (no skill system)


# ---------------------------------------------------------------------------
# Phase 4 — TUI menu regression
# ---------------------------------------------------------------------------

def test_tui_menu_still_has_three_targets():
    menu = cli._build_install_menu()
    assert [item.label for item in menu.items] == ["OpenCode", "Antigravity", "Visual Studio Code"]
    assert len(menu.items) == 3
    assert all(item.keep_tui for item in menu.items)


# ---------------------------------------------------------------------------
# Original tests — preserved
# ---------------------------------------------------------------------------

def test_install_opencode_merges_only_context_life(tmp_path: Path):
    config_path = tmp_path / ".config" / "opencode" / "opencode.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        '{\n  // existing config\n  "theme": "dark",\n  "mcp": {\n    "existing": {"enabled": false,},\n  },\n}\n',
        encoding="utf-8",
    )

    result = install_context_life("opencode", home_dir=tmp_path)

    assert result.changed is True
    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data["theme"] == "dark"
    assert set(data["mcp"].keys()) == {"existing", "context-life"}
    assert data["mcp"]["context-life"] == {
        "type": "local",
        "command": ["context-life"],
        "enabled": True,
    }


def test_install_antigravity_keeps_existing_config(tmp_path: Path):
    config_path = tmp_path / ".gemini" / "antigravity" / "mcp_config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"mcpServers": {"existing": {"command": "old"}}}', encoding="utf-8")

    result = install_context_life("antigravity", home_dir=tmp_path)

    assert result.changed is True
    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert set(data["mcpServers"].keys()) == {"existing", "context-life"}
    assert data["mcpServers"]["context-life"] == {"command": sys.executable, "args": ["-m", "mmcp"]}


def test_install_vscode_writes_context_life_only(monkeypatch: MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))

    result = install_context_life("vscode", home_dir=tmp_path)

    assert result.changed is True
    config_path = tmp_path / "AppData" / "Roaming" / "Code" / "User" / "mcp.json"
    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert set(data["servers"].keys()) == {"context-life"}
    assert data["servers"]["context-life"] == {
        "type": "stdio",
        "command": sys.executable,
        "args": ["-m", "mmcp"],
    }
