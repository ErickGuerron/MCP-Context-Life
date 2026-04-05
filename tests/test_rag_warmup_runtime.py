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
