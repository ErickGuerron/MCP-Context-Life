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


def test_copy_skill_to_opencode_overwrites_existing(
    installer_with_skill: Path, bundled_skill: Path, tmp_path: Path, caplog
):
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


def test_install_skill_for_target_dispatches_antigravity(
    installer_with_skill: Path, bundled_skill: Path, tmp_path: Path
):
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


def test_tui_menu_has_four_install_options():
    menu = cli._build_install_menu()
    item_labels = [item.label for item in menu.items]
    assert item_labels == ["OpenCode", "Antigravity", "Visual Studio Code", "Install context-life-advisor"]
    assert len(menu.items) == 4
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


def test_install_opencode_also_creates_advisor_prompt(tmp_path: Path):
    """install_context_life('opencode') should create the advisor prompt file."""
    config_path = tmp_path / ".config" / "opencode" / "opencode.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"mcp": {}}', encoding="utf-8")

    install_context_life("opencode", home_dir=tmp_path)

    advisor_prompt = tmp_path / ".config" / "opencode" / "prompts" / "context-life-advisor.md"
    assert advisor_prompt.exists()
    content = advisor_prompt.read_text(encoding="utf-8")
    assert "# Context-Life Advisor" in content
    assert "intercept_user_request" in content


def test_install_opencode_adds_advisor_agent_entry(tmp_path: Path):
    """install_context_life('opencode') should add context-life-advisor to agent dict."""
    config_path = tmp_path / ".config" / "opencode" / "opencode.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"agent": {"existing-agent": {}}}', encoding="utf-8")

    install_context_life("opencode", home_dir=tmp_path)

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert "context-life-advisor" in data["agent"]
    assert data["agent"]["context-life-advisor"]["mode"] == "subagent"
    assert data["agent"]["context-life-advisor"]["hidden"] is True
    # Existing agent should NOT be overwritten
    assert "existing-agent" in data["agent"]


def test_deep_merge_does_not_overwrite_existing_agents(tmp_path: Path):
    """_deep_merge should append agents, not replace the agents array."""
    from mmcp.infrastructure.installation.context_life_installer import _deep_merge

    base = {"agent": {"gentle-orchestrator": {"mode": "primary"}, "existing": {"hidden": False}}}
    overlay = {"agent": {"context-life-advisor": {"mode": "subagent"}}}

    result = _deep_merge(base, overlay)

    # Both agents should exist
    assert "gentle-orchestrator" in result["agent"]
    assert "context-life-advisor" in result["agent"]
    # existing agent should still be there
    assert "existing" in result["agent"]
    # gentle-orchestrator should NOT be overwritten
    assert result["agent"]["gentle-orchestrator"]["mode"] == "primary"


def test_detect_stack_finds_gentle_ai(tmp_path: Path):
    """detect_stack should find gentle-orchestrator in agents."""
    from mmcp.infrastructure.installation.context_life_installer import detect_stack

    config_path = tmp_path / ".config" / "opencode" / "opencode.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        '{"agent": {"gentle-orchestrator": {}}, "mcp": {"context-life": {}}}',
        encoding="utf-8",
    )

    stack = detect_stack(tmp_path)

    assert stack.has_gentle_ai is True


def test_detect_stack_finds_engram(tmp_path: Path):
    """detect_stack should find engram in mcp config."""
    from mmcp.infrastructure.installation.context_life_installer import detect_stack

    config_path = tmp_path / ".config" / "opencode" / "opencode.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"mcp": {"engram": {}}}', encoding="utf-8")

    stack = detect_stack(tmp_path)

    assert stack.has_engram is True


def test_detect_stack_returns_false_when_neither_present(tmp_path: Path):
    """detect_stack should return False for both when no gentle-ai or engram."""
    from mmcp.infrastructure.installation.context_life_installer import detect_stack

    config_path = tmp_path / ".config" / "opencode" / "opencode.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"mcp": {"context-life": {}}}', encoding="utf-8")

    stack = detect_stack(tmp_path)

    assert stack.has_gentle_ai is False
    assert stack.has_engram is False


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


def test_install_opencode_with_gentle_ai_patches_orchestrator(tmp_path: Path):
    """install_context_life('opencode') should patch sdd-orchestrator.md when gentle-ai detected."""
    config_path = tmp_path / ".config" / "opencode" / "opencode.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"agent": {"gentle-orchestrator": {}}, "mcp": {}}', encoding="utf-8")

    # Create existing orchestrator prompt with gentle-ai content
    prompts_dir = tmp_path / ".config" / "opencode" / "prompts" / "sdd"
    prompts_dir.mkdir(parents=True)
    orch_path = prompts_dir / "sdd-orchestrator.md"
    orch_path.write_text(
        "You are a COORDINATOR\n\n## Delegation Rules\n",
        encoding="utf-8",
    )

    install_context_life("opencode", home_dir=tmp_path)

    # Orchestrator should be patched with advisor integration
    content = orch_path.read_text(encoding="utf-8")
    assert "context-life-advisor" in content
    assert "Context-Life Advisor Integration" in content


def test_install_opencode_without_gentle_ai_does_not_patch_orchestrator(tmp_path: Path):
    """Without gentle-ai, orchestrator.md should NOT be patched."""
    config_path = tmp_path / ".config" / "opencode" / "opencode.json"
    config_path.parent.mkdir(parents=True)
    # No gentle-orchestrator, no engram
    config_path.write_text('{"agent": {}, "mcp": {"context-life": {}}}', encoding="utf-8")

    # Create orchestrator that would be patched if detected
    prompts_dir = tmp_path / ".config" / "opencode" / "prompts" / "sdd"
    prompts_dir.mkdir(parents=True)
    orch_path = prompts_dir / "sdd-orchestrator.md"
    original = "You are a COORDINATOR\n\n## Delegation Rules\n"
    orch_path.write_text(original, encoding="utf-8")

    install_context_life("opencode", home_dir=tmp_path)

    # Content should remain unchanged
    content = orch_path.read_text(encoding="utf-8")
    assert content == original
    assert "Context-Life Advisor Integration" not in content


def test_get_advisor_prompt_content_with_gentle_ai_and_engram(tmp_path: Path):
    """Advisor prompt should include full D4 with history awareness when both detected."""
    from mmcp.infrastructure.installation.context_life_installer import StackDetection, _get_advisor_prompt_content

    stack = StackDetection(has_gentle_ai=True, has_engram=True)
    content = _get_advisor_prompt_content(stack)

    assert "D4 History Awareness (Engram)" in content
    assert "Strict TDD Question" in content or "test suite" in content.lower()
    assert "Check Engram for conflicting past decisions" in content


def test_get_advisor_prompt_content_with_engram_only(tmp_path: Path):
    """Advisor prompt should include Engram access but no TDD questions without gentle-ai."""
    from mmcp.infrastructure.installation.context_life_installer import StackDetection, _get_advisor_prompt_content

    stack = StackDetection(has_gentle_ai=False, has_engram=True)
    content = _get_advisor_prompt_content(stack)

    assert "Check Engram for conflicting past decisions" in content
    assert "Strict TDD Question" not in content


def test_get_advisor_prompt_content_without_engram(tmp_path: Path):
    """Advisor prompt should skip history awareness when no engram."""
    from mmcp.infrastructure.installation.context_life_installer import StackDetection, _get_advisor_prompt_content

    stack = StackDetection(has_gentle_ai=False, has_engram=False)
    content = _get_advisor_prompt_content(stack)

    assert "Check Engram" not in content
    assert "intercept_user_request" in content


def test_install_context_life_advisor_idempotent(tmp_path: Path):
    """Calling install twice via install_context_life should not duplicate the agent entry."""
    config_path = tmp_path / ".config" / "opencode" / "opencode.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{}", encoding="utf-8")

    # First call via install_context_life (which writes to disk)
    install_context_life("opencode", home_dir=tmp_path)
    data1 = json.loads(config_path.read_text(encoding="utf-8"))

    # Second call (idempotent - should not duplicate)
    install_context_life("opencode", home_dir=tmp_path)
    data2 = json.loads(config_path.read_text(encoding="utf-8"))

    # Should have exactly one context-life-advisor entry
    assert "context-life-advisor" in data2["agent"]
    assert len(data2["agent"]) == 1  # Only advisor, no duplicates
    assert data1["agent"] == data2["agent"]  # Same content
