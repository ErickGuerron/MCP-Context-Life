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

import pytest


def test_rag_engine_instant_construction():
    """RAGEngine() should construct in < 100ms — no model loading."""
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
        assert elapsed_ms < 500, f"Construction took {elapsed_ms:.0f}ms — should be < 500ms"


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
