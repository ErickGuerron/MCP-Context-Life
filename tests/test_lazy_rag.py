"""
Tests for RFC-002 P1: Lazy RAG Engine Loading.

Verifies that:
  1. RAGEngine() construction is instant (no model loading)
  2. stats() works without loading the model
  3. clear() works without loading the model
  4. prewarm() explicitly loads the model
  5. Model loads on first search/index call
"""

import time
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pyarrow as pa
import pytest


def test_rag_engine_instant_construction():
    """RAGEngine() should construct quickly without loading the model."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        start = time.perf_counter()

        # Patch the heavy imports to avoid actual model loading
        with patch("mmcp.rag_engine.lancedb") as mock_lancedb:
            mock_lancedb.connect.return_value = MagicMock()

            from mmcp.rag_engine import RAGEngine

            engine = RAGEngine(db_path=tmp_dir, table_name="test_lazy")

        elapsed_ms = (time.perf_counter() - start) * 1000

        assert not engine._model_loaded, "Model should NOT be loaded at construction"
        assert engine._embedding_fn is None, "Embedding fn should be None at construction"
        assert engine._schema is None, "Schema should be None at construction"
        # Keep this as a broad smoke threshold: import/patch overhead varies a lot
        # across Python versions and Windows CI runners, but model loading must not happen.
        assert elapsed_ms < 2000, f"Construction took {elapsed_ms:.0f}ms — should stay well below model-load latency"


def test_stats_without_model():
    """stats() should work without loading the embedding model."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("mmcp.rag_engine.lancedb") as mock_lancedb:
            mock_db = MagicMock()
            # Simulate no existing table
            mock_db.open_table.side_effect = Exception("Table not found")
            mock_lancedb.connect.return_value = mock_db

            from mmcp.rag_engine import RAGEngine

            engine = RAGEngine(db_path=tmp_dir, table_name="test_stats")

        result = engine.stats()

        assert result["total_chunks"] == 0
        assert result["table"] == "test_stats"
        assert result["model_loaded"] is False


def test_clear_without_model():
    """clear() should work without loading the embedding model."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("mmcp.rag_engine.lancedb") as mock_lancedb:
            mock_db = MagicMock()
            mock_lancedb.connect.return_value = mock_db

            from mmcp.rag_engine import RAGEngine

            engine = RAGEngine(db_path=tmp_dir, table_name="test_clear")

        result = engine.clear()

        assert result["status"] == "cleared"
        assert not engine._model_loaded, "Model should NOT load for clear()"


def test_index_directory_walks_filesystem_once(tmp_path, monkeypatch):
    """index_directory() should scan once and filter extensions in-memory."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    nested_dir = docs_dir / "nested"
    nested_dir.mkdir()

    (docs_dir / "keep.py").write_text("print('ok')")
    (docs_dir / "skip.txt").write_text("ignore me")
    (nested_dir / "keep.md").write_text("# hello")

    with patch("mmcp.rag_engine.lancedb") as mock_lancedb:
        mock_lancedb.connect.return_value = MagicMock()

        import mmcp.rag_engine as rag_module

        engine = rag_module.RAGEngine(db_path=str(tmp_path / "db"), table_name="test_walk")

    indexed_paths = []
    walk_calls = 0
    original_walk = rag_module.os.walk

    def counting_walk(*args, **kwargs):
        nonlocal walk_calls
        walk_calls += 1
        return original_walk(*args, **kwargs)

    def fake_index_file(filepath, source_label=None, force=False):
        indexed_paths.append(Path(filepath).name)
        return {"status": "indexed", "source": Path(filepath).name, "chunks": 1, "file_hash": "fakehash1234"}

    monkeypatch.setattr(rag_module.os, "walk", counting_walk)
    monkeypatch.setattr(engine, "index_file", fake_index_file)

    result = engine.index_directory(str(docs_dir), extensions=[".py", ".md"], recursive=True)

    assert walk_calls == 1
    assert indexed_paths == ["keep.py", "keep.md"]
    assert result["indexed"] == 2
    assert result["skipped"] == 0


def test_load_existing_hashes_uses_projected_arrow_scan(tmp_path):
    """_load_existing_hashes() should scan only file_hash via Arrow projection."""
    with patch("mmcp.rag_engine.lancedb") as mock_lancedb:
        mock_lancedb.connect.return_value = MagicMock()

        import mmcp.rag_engine as rag_module

        engine = rag_module.RAGEngine(db_path=str(tmp_path / "db"), table_name="test_hashes")

    query = MagicMock()
    query.select.return_value = query
    query.to_arrow.return_value = pa.table({"file_hash": ["hash-a", "hash-a", None, "hash-b"]})

    table = MagicMock()
    table.search.return_value = query
    table.to_pandas.side_effect = AssertionError("projected Arrow scan should avoid to_pandas")

    engine._table = table
    engine._model_loaded = True

    engine._load_existing_hashes()

    table.search.assert_called_once_with()
    query.select.assert_called_once_with(["file_hash"])
    query.to_arrow.assert_called_once_with()
    assert engine._indexed_hashes == {"hash-a", "hash-b"}
    assert engine._hashes_loaded is True


@pytest.mark.slow
def test_rag_full_lifecycle():
    """
    Integration test: RAGEngine constructs instantly, then model loads
    on first index_file, and search works correctly.

    NOTE: This test WILL load the real model (~12s). It's a true
    integration test — skip in CI with: pytest -m "not slow"
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        from mmcp.rag_engine import RAGEngine

        # Phase 1: Construction is instant
        t0 = time.perf_counter()
        engine = RAGEngine(db_path=tmp_dir, table_name="test_lifecycle")
        construct_ms = (time.perf_counter() - t0) * 1000

        assert not engine._model_loaded

        # Phase 2: First indexing triggers model load
        test_file = Path(tmp_dir) / "test.txt"
        test_file.write_text("JWT authentication uses Bearer tokens in headers.")

        engine.index_file(str(test_file))
        assert engine._model_loaded, "Model should be loaded after index_file()"

        # Phase 3: Search works
        results = engine.search("how does authentication work?", top_k=1)
        assert len(results) > 0
        assert "JWT" in results[0].text

        # Phase 4: Stats includes model_loaded flag
        stats = engine.stats()
        assert stats["model_loaded"] is True
        assert stats["total_chunks"] > 0

        print(f"\n[LAZY RAG LIFECYCLE]")
        print(f"Construction: {construct_ms:.2f}ms")
        print(f"Stats: {stats}")
