from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_update_scoop_hash_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "update-scoop-hash.py"
    spec = spec_from_file_location("update_scoop_hash", script_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_update_scoop_manifest_replaces_empty_hashes(tmp_path, monkeypatch):
    bucket = tmp_path / "bucket"
    bucket.mkdir()
    manifest = bucket / "context-life.json"
    manifest.write_text(
        '{"hash": "", "architecture": {"amd64": {"hash": ""}, "arm64": {"hash": "old"}}}',
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    update_scoop_manifest = _load_update_scoop_hash_module().update_scoop_manifest
    update_scoop_manifest("abc123", "0.8.7")

    assert manifest.read_text(encoding="utf-8") == (
        '{"hash": "abc123", "architecture": {"amd64": {"hash": "abc123"}, "arm64": {"hash": "abc123"}}}'
    )
