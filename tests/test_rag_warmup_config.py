from pathlib import Path

from mmcp.config import load_config, save_config


def test_load_config_reads_rag_warmup_mode(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[rag]\nwarmup_mode = "startup"\ntop_k = 7\n',
        encoding="utf-8",
    )

    cfg = load_config(str(config_path))

    assert cfg.rag_warmup_mode == "startup"
    assert cfg.rag_top_k == 7


def test_load_config_falls_back_to_lazy_for_invalid_warmup_mode(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[rag]\nwarmup_mode = "turbo"\n',
        encoding="utf-8",
    )

    cfg = load_config(str(config_path))

    assert cfg.rag_warmup_mode == "lazy"


def test_save_config_persists_rag_warmup_mode(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    cfg = load_config(str(config_path))
    cfg.rag_warmup_mode = "manual"

    written_path = save_config(cfg, str(config_path))
    content = written_path.read_text(encoding="utf-8")

    assert 'warmup_mode = "manual"' in content


def test_save_config_default_path_preserves_existing_user_paths(tmp_path: Path, monkeypatch):
    config_root = tmp_path / "config-home"
    monkeypatch.setenv("APPDATA", str(config_root))

    config_path = config_root / "context-life" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
[rag]
warmup_mode = "lazy"

[cache]
db_path = "C:/Users/demo/cache/session.db"

[paths]
data_dir = "C:/Users/demo/data"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    cfg = load_config()
    cfg.rag_warmup_mode = "manual"
    cfg.cache_db_path = str(tmp_path / "pytest-cache" / "session.db")
    cfg.data_dir = str(tmp_path / "pytest-data")

    written_path = save_config(cfg)
    content = written_path.read_text(encoding="utf-8")

    assert written_path == config_path
    assert 'warmup_mode = "manual"' in content
    assert 'db_path = "C:/Users/demo/cache/session.db"' in content
    assert 'data_dir = "C:/Users/demo/data"' in content
    assert "pytest-cache" not in content
    assert "pytest-data" not in content
