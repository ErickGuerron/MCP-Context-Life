import json
from pathlib import Path

from mmcp.presentation.app_container import AppContainer
from mmcp.presentation.mcp import server


class FakeKnowledgeStore:
    def __init__(self):
        self.calls = []
        self._model_loaded = False

    def index_file(self, filepath, source_label=None, force=False):
        self.calls.append(("index_file", filepath, source_label, force))
        return {"status": "indexed", "source": Path(filepath).name, "chunks": 1, "file_hash": "abc123"}

    def index_directory(self, dirpath, recursive=True, force=False):
        self.calls.append(("index_directory", dirpath, recursive, force))
        return {"status": "indexed", "indexed": 1, "skipped": 0, "errors": 0, "files": []}

    def search(self, query, top_k=5, max_tokens=0, min_score=0.0, max_chunks_per_source=0):
        self.calls.append(("search", query, top_k, max_tokens, min_score, max_chunks_per_source))
        return [
            type(
                "Result",
                (),
                {"to_dict": lambda self: {"text": "hit", "source": "doc.md", "score": 0.1, "chunk_index": 0}},
            )()
        ]

    def prewarm(self):
        self.calls.append(("prewarm",))
        self._model_loaded = True

    def stats(self):
        self.calls.append(("stats",))
        return {"table": "knowledge", "total_chunks": 1, "unique_files": 1, "model_loaded": self._model_loaded}

    def clear(self):
        self.calls.append(("clear",))
        return {"status": "cleared", "table": "knowledge"}

    def is_model_loaded(self):
        return self._model_loaded


class FakeRAGEngine:
    def __init__(self, db_path, table_name, chunk_size, chunk_overlap):
        self.db_path = db_path
        self.table_name = table_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._model_loaded = False

    def prewarm(self):
        self._model_loaded = True

    def is_model_loaded(self):
        return self._model_loaded

    def index_file(self, filepath, source_label=None, force=False):
        return {"status": "indexed", "source": Path(filepath).name, "chunks": 1, "file_hash": "abc123"}

    def index_directory(self, dirpath, recursive=True, force=False):
        return {"status": "indexed", "indexed": 1, "skipped": 0, "errors": 0, "files": []}

    def search(self, query, top_k=5, max_tokens=0, min_score=0.0, max_chunks_per_source=0):
        result_type = type(
            "Result",
            (),
            {
                "to_dict": lambda self: {
                    "text": "hit",
                    "source": "doc.md",
                    "score": 0.1,
                    "chunk_index": 0,
                }
            },
        )
        return [result_type()]

    def stats(self):
        return {"table": "knowledge", "total_chunks": 1, "unique_files": 1, "model_loaded": self._model_loaded}

    def clear(self):
        return {"status": "cleared", "table": "knowledge"}


def test_knowledge_service_routes_indexing_and_search_and_prewarm(tmp_path):
    from mmcp.application.features.knowledge.service import KnowledgeService

    store = FakeKnowledgeStore()
    service = KnowledgeService(store)

    doc = tmp_path / "doc.md"
    doc.write_text("hello")
    docs = tmp_path / "docs"
    docs.mkdir()

    indexed_file = service.index_knowledge(str(doc))
    indexed_dir = service.index_knowledge(str(docs), recursive=False, force=True)
    searched = service.search_context("hello", top_k=1, max_tokens=10, min_score=0.2, max_chunks_per_source=1)
    warm = service.prewarm_rag_now()
    stats = service.rag_stats()
    cleared = service.clear_knowledge()

    assert store.calls[0] == ("index_file", str(doc), None, False)
    assert store.calls[1] == ("index_directory", str(docs), False, True)
    assert store.calls[2] == ("search", "hello", 1, 10, 0.2, 1)
    assert store.calls[3] == ("prewarm",)
    assert store.calls[4] == ("stats",)
    assert store.calls[5] == ("clear",)
    assert indexed_file["status"] == "indexed"
    assert indexed_dir["indexed"] == 1
    assert searched["results_count"] == 1
    assert warm["model_loaded"] is True
    assert stats["total_chunks"] == 1
    assert cleared["status"] == "cleared"


def test_app_container_reuses_knowledge_service_until_rag_config_changes(monkeypatch, isolated_data_dir, tmp_path):
    from mmcp.infrastructure.environment.config import get_config

    cfg = get_config()
    monkeypatch.setattr(server, "RAGEngine", FakeRAGEngine)
    container = AppContainer()

    cfg.data_dir = str(tmp_path / "rag-a")
    first = container.get_knowledge_service()
    second = container.get_knowledge_service()

    cfg.data_dir = str(tmp_path / "rag-b")
    third = container.get_knowledge_service()

    assert first is second
    assert first.store.db_path.endswith(("rag-a\\lancedb", "rag-a/lancedb"))
    assert third is not first
    assert third.store.db_path.endswith(("rag-b\\lancedb", "rag-b/lancedb"))


def test_server_knowledge_tools_delegate_to_service(monkeypatch, tmp_path):
    class StubService:
        def __init__(self):
            self.calls = []
            self._model_loaded = False

        def index_file(self, path, force=False):
            self.calls.append(("index_file", path, force))
            return {"status": "indexed"}

        def index_directory(self, path, recursive=True, force=False):
            self.calls.append(("index_directory", path, recursive, force))
            return {"status": "indexed"}

        def search(self, query, top_k=5, max_tokens=0, min_score=0.0, max_chunks_per_source=0):
            self.calls.append(("search", query, top_k, max_tokens, min_score, max_chunks_per_source))
            return [
                type(
                    "Result",
                    (),
                    {"to_dict": lambda self: {"text": "hit", "source": "doc.md", "score": 0.1, "chunk_index": 0}},
                )()
            ]

        def prewarm(self):
            self.calls.append(("prewarm",))
            self._model_loaded = True
            return {"status": "ready"}

        def stats(self):
            self.calls.append(("rag_stats",))
            return {"total_chunks": 0}

        def clear(self):
            self.calls.append(("clear",))
            return {"status": "cleared"}

    service = StubService()
    monkeypatch.setattr(server, "_get_rag_engine", lambda: service)
    doc = tmp_path / "doc.md"
    doc.write_text("hello")

    assert server.index_knowledge(str(doc)) == '{"status": "indexed"}'
    assert server.search_context("query") == (
        '{"query": "query", "results_count": 1, "results": ['
        '{"text": "hit", "source": "doc.md", "score": 0.1, "chunk_index": 0}]}'
    )
    assert json.loads(server.prewarm_rag())["status"] == "ready"
    assert server.rag_stats() == '{"total_chunks": 0}'
    assert server.clear_knowledge() == '{"status": "cleared"}'
    assert service.calls == [
        ("index_file", str(doc), False),
        ("search", "query", 5, 0, 0.0, 0),
        ("prewarm",),
        ("rag_stats",),
        ("clear",),
    ]
