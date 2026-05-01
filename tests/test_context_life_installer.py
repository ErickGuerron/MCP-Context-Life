import json
import sys

import mmcp.presentation.cli.cli as cli
from mmcp.infrastructure.installation.context_life_installer import install_context_life


def test_install_opencode_merges_only_context_life(tmp_path):
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


def test_install_antigravity_keeps_existing_config(tmp_path):
    config_path = tmp_path / ".gemini" / "antigravity" / "mcp_config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"mcpServers": {"existing": {"command": "old"}}}', encoding="utf-8")

    result = install_context_life("antigravity", home_dir=tmp_path)

    assert result.changed is True
    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert set(data["mcpServers"].keys()) == {"existing", "context-life"}
    assert data["mcpServers"]["context-life"] == {"command": sys.executable, "args": ["-m", "mmcp"]}


def test_install_vscode_writes_context_life_only(monkeypatch, tmp_path):
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


def test_install_menu_contains_three_targets():
    menu = cli._build_install_menu()

    assert [item.label for item in menu.items] == ["OpenCode", "Antigravity", "Visual Studio Code"]
    assert all(item.keep_tui for item in menu.items)
