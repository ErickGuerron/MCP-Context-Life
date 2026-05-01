import pytest

from mmcp.infrastructure.environment.config import get_config
from mmcp.presentation.app_container import AppContainer
from mmcp.presentation.mcp import server


class FakeRAGEngine:
    def __init__(self, db_path, table_name, chunk_size, chunk_overlap):
        self.db_path = db_path
        self.table_name = table_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._model_loaded = False

    def prewarm(self):
        self._model_loaded = True


class FakeSessionStore:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        self.calls = []

    def record_usage(self, event):
        self.calls.append(event)


class LocalTokenBudget:
    def __init__(self, max_tokens, safety_buffer):
        self.max_tokens = max_tokens
        self.safety_buffer = safety_buffer


class ServerTokenBudget:
    def __init__(self, max_tokens, safety_buffer):
        self.max_tokens = max_tokens
        self.safety_buffer = safety_buffer


def test_container_reuses_token_budget_until_config_changes(isolated_data_dir):
    container = AppContainer()

    first = container.get_token_budget()
    second = container.get_token_budget()

    assert first is second
    assert first.max_tokens == get_config().token_budget_default


def test_container_prefers_local_token_budget_class_over_server_compatibility_override(
    monkeypatch, isolated_data_dir
):
    from mmcp.presentation import app_container as app_container_module

    monkeypatch.setattr(app_container_module, "TokenBudget", LocalTokenBudget)
    monkeypatch.setattr(server, "TokenBudget", ServerTokenBudget, raising=False)

    container = AppContainer()
    budget = container.get_token_budget()

    assert isinstance(budget, LocalTokenBudget)
    assert not isinstance(budget, ServerTokenBudget)


def test_container_rebuilds_token_budget_when_config_changes(isolated_data_dir):
    cfg = get_config()
    container = AppContainer()

    first = container.get_token_budget()
    cfg.token_budget_default = 64_000

    second = container.get_token_budget()

    assert first is not second
    assert second.max_tokens == 64_000


def test_container_reuses_cache_loop_until_config_changes(isolated_data_dir):
    container = AppContainer()

    first = container.get_cache_loop()
    second = container.get_cache_loop()

    assert first is second


def test_container_rebuilds_cache_loop_when_config_changes(isolated_data_dir):
    cfg = get_config()
    container = AppContainer()

    first = container.get_cache_loop()
    cfg.cache_max_entries = 99

    second = container.get_cache_loop()

    assert first is not second


def test_container_reuses_rag_engine_until_config_changes(monkeypatch, isolated_data_dir, tmp_path):
    from mmcp.presentation import app_container as app_container_module

    cfg = get_config()
    monkeypatch.setattr(app_container_module, "RAGEngine", FakeRAGEngine)
    container = AppContainer()

    cfg.data_dir = str(tmp_path / "rag-a")
    first = container.get_rag_engine()
    second = container.get_rag_engine()

    assert first is second
    assert first.db_path.endswith(("rag-a\\lancedb", "rag-a/lancedb"))


def test_container_prefers_local_rag_engine_class_over_server_compatibility_override(
    monkeypatch, isolated_data_dir, tmp_path
):
    from mmcp.presentation import app_container as app_container_module

    class LocalRAGEngine(FakeRAGEngine):
        pass

    class ServerRAGEngine(FakeRAGEngine):
        pass

    monkeypatch.setattr(app_container_module, "RAGEngine", LocalRAGEngine)
    monkeypatch.setattr(server, "RAGEngine", ServerRAGEngine, raising=False)

    cfg = get_config()
    container = AppContainer()

    cfg.data_dir = str(tmp_path / "rag-a")
    engine = container.get_rag_engine()

    assert isinstance(engine, LocalRAGEngine)
    assert not isinstance(engine, ServerRAGEngine)


def test_server_does_not_expose_container_singletons_as_module_attributes():
    assert hasattr(server, "_rag_engine")


def test_container_rebuilds_rag_engine_when_config_changes(monkeypatch, isolated_data_dir, tmp_path):
    from mmcp.presentation import app_container as app_container_module

    cfg = get_config()
    monkeypatch.setattr(app_container_module, "RAGEngine", FakeRAGEngine)
    container = AppContainer()

    cfg.data_dir = str(tmp_path / "rag-a")
    first = container.get_rag_engine()

    cfg.data_dir = str(tmp_path / "rag-b")
    second = container.get_rag_engine()

    assert first is not second
    assert first.db_path.endswith(("rag-a\\lancedb", "rag-a/lancedb"))
    assert second.db_path.endswith(("rag-b\\lancedb", "rag-b/lancedb"))


def test_container_reuses_telemetry_service_until_cache_db_changes(monkeypatch, isolated_data_dir, tmp_path):
    from mmcp.presentation import app_container as app_container_module

    cfg = get_config()
    monkeypatch.setattr(app_container_module, "SessionStore", FakeSessionStore)
    container = AppContainer()

    cfg.cache_db_path = str(tmp_path / "telemetry-a" / "session.db")
    first = container.get_telemetry_service()
    second = container.get_telemetry_service()

    cfg.cache_db_path = str(tmp_path / "telemetry-b" / "session.db")
    third = container.get_telemetry_service()

    assert first is second
    assert first.store.db_path.endswith(("telemetry-a\\session.db", "telemetry-a/session.db"))
    assert third is not first
    assert third.store.db_path.endswith(("telemetry-b\\session.db", "telemetry-b/session.db"))
