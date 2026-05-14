import re
from types import SimpleNamespace

from rich.console import Console

import mmcp.presentation.cli.cli as cli
import mmcp.presentation.cli.upgrade as upgrade
from mmcp.presentation.cli.upgrade import ErrorCode


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

    # Config menu order: RAG Warmup, Governance, Install, Config Model, Upgrade
    # Governance was inserted at index 1, so Upgrade is now at index 4
    assert menu.items[4].label == "Upgrade Context-Life"
    assert menu.items[4].keep_tui is True


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

    assert "update the mcp?" in preview_text
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


def test_upgrade_failure_shows_error_code_e99_with_stderr(monkeypatch):
    """Unknown error (E99) shows structured panel with raw stderr."""
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
    assert "e99" in output
    assert "unknown error" in output
    assert "boom" in output
    assert "enter: try again" in output
    assert "remediation:" in output


# =============================================================================
# ErrorCode Classification Tests
# =============================================================================


class TestParseUpgradeError:
    """Tests for _parse_upgrade_error error code classification."""

    def test_e01_network_connection_timeout(self):
        """E01 matched when connection times out."""
        stderr = (
            "WARNING: Retrying (Retry(total=3, connect=None, read=None, "
            "redirect=None, status=None)) in 1.0 seconds... "
            "Download error: ConnectionTimeoutError: Connection timeout"
        )
        result = upgrade._parse_upgrade_error(stderr)
        assert result == ErrorCode.E01

    def test_e01_dns_failure(self):
        """E01 matched on DNS failure."""
        stderr = "ERROR: Could not fetch URL https://pypi.org/simple/abc/: DNS failure"
        result = upgrade._parse_upgrade_error(stderr)
        assert result == ErrorCode.E01

    def test_e01_econnrefused(self):
        """E01 matched on ECONNREFUSED."""
        stderr = "ERROR: Could not install packages due to an OSError: [Errno 111] ECONNREFUSED"
        result = upgrade._parse_upgrade_error(stderr)
        assert result == ErrorCode.E01

    def test_e01_https_error(self):
        """E01 matched on HTTPS errors."""
        stderr = "HTTPSError 500: Internal Server Error"
        result = upgrade._parse_upgrade_error(stderr)
        assert result == ErrorCode.E01

    def test_e02_permission_denied_eacces(self):
        """E02 matched on EACCES permission error."""
        stderr = (
            "ERROR: Could not install packages due to an OSError: "
            "[Errno 13] EACCES: permission denied: "
            "'/usr/local/lib/python3.11/site-packages'"
        )
        result = upgrade._parse_upgrade_error(stderr)
        assert result == ErrorCode.E02

    def test_e02_permission_denied_eperm(self):
        """E02 matched on EPERM."""
        stderr = "ERROR: Could not install packages due to an OSError: [Errno 1] EPERM: operation not permitted"
        result = upgrade._parse_upgrade_error(stderr)
        assert result == ErrorCode.E02

    def test_e03_pep668_externally_managed(self):
        """E03 matched on PEP 668 externally managed Python."""
        stderr = (
            "ERROR: Cannot install to target directory "
            "'/usr/lib/python3.11/dist-packages' because it is externally "
            "managed. Traceback (most recent call last): pep 668"
        )
        result = upgrade._parse_upgrade_error(stderr)
        assert result == ErrorCode.E03

    def test_e03_pep668_not_writable(self):
        """E03 matched when 'not writable' in stderr."""
        stderr = "ERROR: The column 'abc' is not writable. externally managed"
        result = upgrade._parse_upgrade_error(stderr)
        assert result == ErrorCode.E03

    def test_e04_version_not_found_404(self):
        """E04 matched on HTTP 404."""
        stderr = "ERROR: HTTP error 404: Not Found"
        result = upgrade._parse_upgrade_error(stderr)
        assert result == ErrorCode.E04

    def test_e04_version_not_found_pypi(self):
        """E04 matched when package not on PyPI."""
        stderr = "ERROR: Package not found on PyPI: nonexistent-package-xyz"
        result = upgrade._parse_upgrade_error(stderr)
        assert result == ErrorCode.E04

    def test_e05_checksum_mismatch(self):
        """E05 matched on hash/checksum verification failure."""
        stderr = "ERROR: HERE IS THE HASH: aaaa2222. The hashes do not match."
        result = upgrade._parse_upgrade_error(stderr)
        assert result == ErrorCode.E05

    def test_e99_unknown_error(self):
        """E99 is fallback when no specific code matches."""
        stderr = "some random error that doesn't match any pattern"
        result = upgrade._parse_upgrade_error(stderr)
        assert result == ErrorCode.E99

    def test_e03_priority_over_e01(self):
        """E03 takes priority over E01 when both patterns could match."""
        # PEP 668 message with connection error in the text
        stderr = "WARNING: externally managed Python. Download error: ConnectionTimeout"
        result = upgrade._parse_upgrade_error(stderr)
        assert result == ErrorCode.E03

    def test_e01_priority_over_e02(self):
        """E01 takes priority over E02 when both patterns could match."""
        # ECONNREFUSED with permission-like message
        stderr = "[Errno 111] ECONNREFUSED permission denied"
        result = upgrade._parse_upgrade_error(stderr)
        assert result == ErrorCode.E01

    def test_e04_priority_over_e05(self):
        """E04 takes priority over E05 when both patterns could match."""
        stderr = "HTTP error 404: Not Found hash mismatch"
        result = upgrade._parse_upgrade_error(stderr)
        assert result == ErrorCode.E04


class TestBuildFailurePanelWithErrorCode:
    """Tests for _build_failure_panel with error codes."""

    def test_e01_panel_shows_network_fixes(self):
        """E01 panel shows network remediation steps."""
        panel = upgrade._build_failure_panel(
            old_version="0.4.0",
            target_label="v0.7.1",
            install_target="git+https://github.com/example/repo.git@v0.7.1",
            stderr_text=None,
            error_code=ErrorCode.E01,
        )
        preview = Console(record=True, width=100)
        preview.print(panel)
        text = preview.export_text()
        assert "E01" in text
        assert "Network failure" in text
        assert "internet connection" in text.lower()
        assert "proxy" in text.lower()
        assert "stderr" not in text.lower()

    def test_e02_panel_shows_permission_fixes(self):
        """E02 panel shows permission remediation steps."""
        panel = upgrade._build_failure_panel(
            old_version="0.4.0",
            target_label="v0.7.1",
            install_target="git+https://github.com/example/repo.git@v0.7.1",
            stderr_text=None,
            error_code=ErrorCode.E02,
        )
        preview = Console(record=True, width=100)
        preview.print(panel)
        text = preview.export_text()
        assert "E02" in text
        assert "Permission denied" in text
        assert "administrator" in text.lower() or "user" in text.lower()

    def test_e03_panel_shows_pep668_fixes(self):
        """E03 panel shows PEP 668 remediation steps."""
        panel = upgrade._build_failure_panel(
            old_version="0.4.0",
            target_label="v0.7.1",
            install_target="git+https://github.com/example/repo.git@v0.7.1",
            stderr_text=None,
            error_code=ErrorCode.E03,
        )
        preview = Console(record=True, width=100)
        preview.print(panel)
        text = preview.export_text()
        assert "E03" in text
        assert "PEP 668" in text
        assert "uv tool install" in text.lower() or "virtual environment" in text.lower()

    def test_e04_panel_shows_version_fixes(self):
        """E04 panel shows version not found remediation."""
        panel = upgrade._build_failure_panel(
            old_version="0.4.0",
            target_label="v0.7.1",
            install_target="git+https://github.com/example/repo.git@v0.7.1",
            stderr_text=None,
            error_code=ErrorCode.E04,
        )
        preview = Console(record=True, width=100)
        preview.print(panel)
        text = preview.export_text()
        assert "E04" in text
        assert "Version not found" in text
        assert "pypi" in text.lower() or "github" in text.lower()

    def test_e05_panel_shows_checksum_fixes(self):
        """E05 panel shows checksum mismatch remediation."""
        panel = upgrade._build_failure_panel(
            old_version="0.4.0",
            target_label="v0.7.1",
            install_target="git+https://github.com/example/repo.git@v0.7.1",
            stderr_text=None,
            error_code=ErrorCode.E05,
        )
        preview = Console(record=True, width=100)
        preview.print(panel)
        text = preview.export_text()
        assert "E05" in text
        assert "Checksum" in text
        assert "retry" in text.lower()

    def test_e99_panel_includes_raw_stderr(self):
        """E99 panel includes raw stderr output."""
        raw_stderr = "some error message here"
        panel = upgrade._build_failure_panel(
            old_version="0.4.0",
            target_label="v0.7.1",
            install_target="git+https://github.com/example/repo.git@v0.7.1",
            stderr_text=raw_stderr,
            error_code=ErrorCode.E99,
        )
        preview = Console(record=True, width=100)
        preview.print(panel)
        text = preview.export_text()
        assert "E99" in text
        assert "Unknown error" in text
        assert raw_stderr in text

    def test_e99_panel_without_stderr(self):
        """E99 panel shows unknown error even without stderr."""
        panel = upgrade._build_failure_panel(
            old_version="0.4.0",
            target_label="v0.7.1",
            install_target="git+https://github.com/example/repo.git@v0.7.1",
            stderr_text=None,
            error_code=ErrorCode.E99,
        )
        preview = Console(record=True, width=100)
        preview.print(panel)
        text = preview.export_text()
        assert "E99" in text
        assert "Unknown error" in text

    def test_no_error_code_falls_back_to_old_behavior(self):
        """Without error_code, falls back to original uv recommendation panel."""
        panel = upgrade._build_failure_panel(
            old_version="0.4.0",
            target_label="v0.7.1",
            install_target="git+https://github.com/example/repo.git@v0.7.1",
            stderr_text="some error",
            error_code=None,
        )
        preview = Console(record=True, width=100)
        preview.print(panel)
        text = preview.export_text()
        assert "install uv first" in text.lower()
        assert "uv tool install" in text
