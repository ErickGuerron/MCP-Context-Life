import re
from types import SimpleNamespace

from rich.console import Console

import mmcp.presentation.cli.cli as cli
import mmcp.presentation.cli.upgrade as upgrade


class _FakeStream:
    def __init__(self):
        self.buffer = []

    def write(self, text):
        self.buffer.append(text)
        return len(text)

    def flush(self):
        return None

    def isatty(self):
        return True


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", text)


def test_upgrade_clears_screen_before_confirmation(monkeypatch):
    stream = _FakeStream()
    console = Console(file=stream, force_terminal=True, width=100)

    monkeypatch.setattr(cli, "CONSOLE", console)
    monkeypatch.setattr(upgrade, "CONSOLE", console)
    monkeypatch.setattr(cli.sys, "stdin", stream)
    monkeypatch.setattr(cli.sys, "stdout", stream)
    monkeypatch.setattr(upgrade.sys, "stdin", stream)
    monkeypatch.setattr(upgrade.sys, "stdout", stream)
    monkeypatch.setattr(upgrade, "_read_tui_key", lambda: "enter")

    upgrade.do_upgrade(target_version="v9.9.9", dry_run=True)

    output = "".join(stream.buffer)
    assert "\x1b[2j\x1b[h" in output.lower()
    assert "context-life upgrade" in output.lower()


def test_upgrade_clear_screen_uses_cls_on_windows(monkeypatch):
    stream = _FakeStream()
    calls = []

    monkeypatch.setattr(upgrade.os, "name", "nt", raising=False)
    monkeypatch.setattr(upgrade.os, "system", lambda cmd: calls.append(cmd))
    monkeypatch.setattr(upgrade.sys, "stdout", stream)

    upgrade._clear_screen()

    assert calls == ["cls"]


def test_cli_upgrade_delegates_to_dedicated_flow(monkeypatch):
    called = []

    monkeypatch.setattr(upgrade, "do_upgrade", lambda *args, **kwargs: called.append((args, kwargs)))

    cli.do_upgrade(target_version="v1.2.3", dry_run=True)

    assert called == [((), {"target_version": "v1.2.3", "dry_run": True, "inside_tui": False})]


def test_upgrade_menu_item_keeps_tui_modal():
    menu = cli._build_config_menu()

    assert menu.items[1].label == "Upgrade Context-Life"
    assert menu.items[1].keep_tui is True


def test_menu_action_can_keep_tui(monkeypatch):
    stream = _FakeStream()

    result = cli._run_menu_action(
        lambda: "ok",
        stream.write,
        stream.flush,
        "SHOW",
        "EXIT",
        "ENTER",
        "HIDE",
        keep_tui=True,
    )

    assert result == "ok"
    assert "".join(stream.buffer) == ""


def test_upgrade_shows_confirmation_before_install(monkeypatch):
    preview = Console(record=True, width=100)
    preview.print(upgrade._build_confirmation_panel("0.4.0", "v0.7.1", "https://example.test/release", False))
    preview_text = preview.export_text().lower()

    assert "¿querés actualizar el mcp?" in preview_text
    assert "context-life 0.4.0 -> v0.7.1" in preview_text
    assert "enter: continue" in preview_text
    assert "esc/q: cancel" in preview_text

    stream = _FakeStream()
    console = Console(file=stream, force_terminal=True, width=100)

    monkeypatch.setattr(cli, "CONSOLE", console)
    monkeypatch.setattr(upgrade, "CONSOLE", console)
    monkeypatch.setattr(cli.sys, "stdin", stream)
    monkeypatch.setattr(cli.sys, "stdout", stream)
    monkeypatch.setattr(upgrade.sys, "stdin", stream)
    monkeypatch.setattr(upgrade.sys, "stdout", stream)
    versions = iter(["0.4.0", "0.7.1"])
    monkeypatch.setattr(upgrade, "get_version", lambda: next(versions))
    monkeypatch.setattr(upgrade, "_fetch_latest_release", lambda: ("0.7.1", "https://example.test/release"))
    monkeypatch.setattr(
        upgrade.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    key_sequence = iter(["enter", "enter"])
    monkeypatch.setattr(upgrade, "_read_tui_key", lambda: next(key_sequence))

    upgrade.do_upgrade()

    output = _strip_ansi("".join(stream.buffer)).lower()
    assert "upgrade completed successfully" in output
    assert "press enter to return" in output


def test_upgrade_failure_recommends_uv(monkeypatch):
    stream = _FakeStream()
    console = Console(file=stream, force_terminal=True, width=100)

    monkeypatch.setattr(cli, "CONSOLE", console)
    monkeypatch.setattr(upgrade, "CONSOLE", console)
    monkeypatch.setattr(cli.sys, "stdin", stream)
    monkeypatch.setattr(cli.sys, "stdout", stream)
    monkeypatch.setattr(upgrade.sys, "stdin", stream)
    monkeypatch.setattr(upgrade.sys, "stdout", stream)
    monkeypatch.setattr(upgrade, "get_version", lambda: "0.4.0")
    monkeypatch.setattr(upgrade, "_fetch_latest_release", lambda: ("0.7.1", "https://example.test/release"))
    monkeypatch.setattr(
        upgrade.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )
    key_sequence = iter(["enter", "esc"])
    monkeypatch.setattr(upgrade, "_read_tui_key", lambda: next(key_sequence))

    upgrade.do_upgrade()

    output = _strip_ansi("".join(stream.buffer)).lower()
    assert "recommended:" in output
    assert "install uv first" in output
    assert "python -m pip install uv" in output
    assert "uv tool install --force" in output
    assert "enter: try again" in output
