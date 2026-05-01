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


def test_upgrade_uses_alt_screen_to_avoid_leaving_terminal_traces(monkeypatch):
    stream = _FakeStream()
    console = Console(file=stream, force_terminal=True, width=100)

    monkeypatch.setattr(cli, "CONSOLE", console)
    monkeypatch.setattr(upgrade, "CONSOLE", console)
    monkeypatch.setattr(cli.sys, "stdin", stream)
    monkeypatch.setattr(cli.sys, "stdout", stream)
    monkeypatch.setattr(upgrade.sys, "stdin", stream)
    monkeypatch.setattr(upgrade.sys, "stdout", stream)

    upgrade.do_upgrade(target_version="v9.9.9", dry_run=True)

    output = "".join(stream.buffer)
    assert "\x1b[?1049h" in output
    assert "\x1b[?1049l" in output
