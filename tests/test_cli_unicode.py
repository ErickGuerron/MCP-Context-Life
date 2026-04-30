import mmcp.presentation.cli.cli as cli


class _FakeStream:
    def __init__(self):
        self.calls = []

    def reconfigure(self, **kwargs):
        self.calls.append(kwargs)


def test_ensure_utf8_output_reconfigures_streams(monkeypatch):
    stdout = _FakeStream()
    stderr = _FakeStream()

    monkeypatch.setattr(cli.sys, "stdout", stdout)
    monkeypatch.setattr(cli.sys, "stderr", stderr)

    changed = cli._ensure_utf8_output()

    assert changed is True
    assert stdout.calls == [{"encoding": "utf-8", "errors": "replace"}]
    assert stderr.calls == [{"encoding": "utf-8", "errors": "replace"}]
