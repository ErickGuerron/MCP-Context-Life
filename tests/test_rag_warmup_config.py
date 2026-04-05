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
