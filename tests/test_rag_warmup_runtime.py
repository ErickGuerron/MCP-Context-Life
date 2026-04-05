from mmcp import server
from mmcp.config import get_config


class FakeRAGEngine:
    def __init__(self, db_path, table_name, chunk_size, chunk_overlap):
        self.db_path = db_path
        self.table_name = table_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._model_loaded = False
        self.prewarm_calls = 0

    def prewarm(self):
        self.prewarm_calls += 1
        self._model_loaded = True


def test_initialize_runtime_prewarms_on_startup_mode(monkeypatch, isolated_data_dir):
    cfg = get_config()
    cfg.rag_warmup_mode = "startup"
    monkeypatch.setattr(server, "RAGEngine", FakeRAGEngine)
    server.reset_runtime_state()

    result = server.initialize_runtime()

    assert result["mode"] == "startup"
    assert result["prewarmed"] is True
    assert server._rag_engine is not None
    assert server._rag_engine.prewarm_calls == 1


def test_initialize_runtime_keeps_lazy_mode_cold(monkeypatch, isolated_data_dir):
    cfg = get_config()
    cfg.rag_warmup_mode = "lazy"
    monkeypatch.setattr(server, "RAGEngine", FakeRAGEngine)
    server.reset_runtime_state()

    result = server.initialize_runtime()

    assert result["mode"] == "lazy"
    assert result["prewarmed"] is False
    assert server._rag_engine is None


def test_prewarm_rag_now_explicitly_warms_manual_mode(monkeypatch, isolated_data_dir):
    cfg = get_config()
    cfg.rag_warmup_mode = "manual"
    monkeypatch.setattr(server, "RAGEngine", FakeRAGEngine)
    server.reset_runtime_state()

    result = server.prewarm_rag_now()

    assert result["mode"] == "manual"
    assert result["already_loaded"] is False
    assert result["model_loaded"] is True
    assert server._rag_engine is not None
    assert server._rag_engine.prewarm_calls == 1


def test_initialize_runtime_reacts_to_warmup_mode_changes_without_reset(monkeypatch, isolated_data_dir):
    cfg = get_config()
    monkeypatch.setattr(server, "RAGEngine", FakeRAGEngine)
    server.reset_runtime_state()

    cfg.rag_warmup_mode = "lazy"
    first = server.initialize_runtime()

    cfg.rag_warmup_mode = "startup"
    second = server.initialize_runtime()

    assert first["status"] == "initialized"
    assert first["prewarmed"] is False
    assert second["status"] == "initialized"
    assert second["mode"] == "startup"
    assert second["prewarmed"] is True
    assert server._rag_engine is not None
    assert server._rag_engine.prewarm_calls == 1


def test_get_rag_engine_rebuilds_when_rag_config_changes(monkeypatch, isolated_data_dir, tmp_path):
    cfg = get_config()
    monkeypatch.setattr(server, "RAGEngine", FakeRAGEngine)
    server.reset_runtime_state()

    cfg.data_dir = str(tmp_path / "rag-a")
    first_engine = server._get_rag_engine()

    cfg.data_dir = str(tmp_path / "rag-b")
    second_engine = server._get_rag_engine()

    assert first_engine is not second_engine
    assert first_engine.db_path.endswith(("rag-a\\lancedb", "rag-a/lancedb"))
    assert second_engine.db_path.endswith(("rag-b\\lancedb", "rag-b/lancedb"))
