"""
Tests for RFC-002 P6: Cross-Session Persistence.

Tests for SessionPersistence with:
- 6.1: RED test for save_state() / load_state() with atomic writes
- 6.2: GREEN implement append-only journal table + state table
- 6.3: GREEN add journal_replay() on startup
- 6.4: REFACTOR: corrupted state archive + fresh start fallback
- 6.5: Add workspace fingerprint persistence
- 6.6: RED test for cross_session_state.enabled: false memory-only mode

These tests should FAIL initially (RED phase) since session_persistence.py
doesn't exist yet.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import time
import json
import sqlite3


def _make_enabled_config(mock_config):
    """Helper to make cross_session_state_enabled=True on a CLConfig."""
    mock_config.cross_session_state_enabled = True
    return mock_config


class TestSessionPersistence:
    """Phase 6 Cross-Session Persistence tests."""

    def test_save_and_load_state(self, tmp_path):
        """save_state() and load_state() roundtrip should return identical data."""
        from mmcp.infrastructure.environment import config as config_module
        from mmcp.infrastructure.persistence.session_persistence import SessionPersistence

        mock_config = config_module.CLConfig()
        mock_config.cross_session_state_enabled = True

        db_path = tmp_path / "test_session.db"

        with patch.object(config_module, "get_config", return_value=mock_config):
            store = SessionPersistence(db_path=db_path)
            test_state = {"key": "value", "number": 42, "list": [1, 2, 3]}

            store.save_state("session-1", test_state)
            loaded = store.load_state("session-1")

        assert loaded == test_state

    def test_atomic_write_preserves_on_failure(self, tmp_path):
        """If write fails midway, prior state should be preserved (not corrupted)."""
        from mmcp.infrastructure.environment import config as config_module
        from mmcp.infrastructure.persistence.session_persistence import SessionPersistence

        mock_config = config_module.CLConfig()
        mock_config.cross_session_state_enabled = True

        db_path = tmp_path / "test_session.db"

        with patch.object(config_module, "get_config", return_value=mock_config):
            store = SessionPersistence(db_path=db_path)
            original = {"key": "original"}
            store.save_state("session-2", original)

            # Try to save invalid state (None)
            try:
                store.save_state("session-2", None)  # type: ignore
            except Exception:
                pass

            # Should still have original
            loaded = store.load_state("session-2")
            assert loaded == original

    def test_journal_replay_on_startup(self, tmp_path):
        """SessionPersistence should replay journal on init to reconstruct state."""
        from mmcp.infrastructure.environment import config as config_module
        from mmcp.infrastructure.persistence.session_persistence import SessionPersistence

        mock_config = config_module.CLConfig()
        mock_config.cross_session_state_enabled = True

        db_path = tmp_path / "test_session.db"

        with patch.object(config_module, "get_config", return_value=mock_config):
            # Save state
            store1 = SessionPersistence(db_path=db_path)
            store1.save_state("session-3", {"from": "journal"})

            # Simulate restart by creating new instance
            store2 = SessionPersistence(db_path=db_path)
            loaded = store2.load_state("session-3")

        assert loaded == {"from": "journal"}

    def test_corrupted_state_archive_and_fresh_start(self, tmp_path):
        """If state is corrupted (invalid JSON), archive it and start fresh."""
        from mmcp.infrastructure.environment import config as config_module
        from mmcp.infrastructure.persistence.session_persistence import SessionPersistence

        mock_config = config_module.CLConfig()
        mock_config.cross_session_state_enabled = True

        db_path = tmp_path / "test_session.db"

        with patch.object(config_module, "get_config", return_value=mock_config):
            store = SessionPersistence(db_path=db_path)
            store.save_state("session-4", {"valid": True})

            # Corrupt both the state AND the journal with invalid JSON
            # so journal_replay cannot recover
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.execute("UPDATE session_state SET state_json = ? WHERE session_id = ?",
                         ("NOT_VALID_JSON{{{", "session-4"))
            # Also corrupt the journal - insert a bad entry that will cause journal_replay to fail
            conn.execute("UPDATE session_journal SET state_json = ? WHERE session_id = ?",
                         ("ALSO_INVALID{{{", "session-4"))
            conn.commit()
            conn.close()

            # Should handle gracefully - archive and start fresh
            store2 = SessionPersistence(db_path=db_path)
            result = store2.load_state("session-4")

        # Should return None (fresh start), not crash
        assert result is None

    def test_workspace_fingerprint_persistence(self, tmp_path):
        """Workspace fingerprint (base_prefix_hash, RAG_hash) should persist."""
        from mmcp.infrastructure.environment import config as config_module
        from mmcp.infrastructure.persistence.session_persistence import SessionPersistence

        mock_config = config_module.CLConfig()
        mock_config.cross_session_state_enabled = True

        db_path = tmp_path / "test_session.db"

        with patch.object(config_module, "get_config", return_value=mock_config):
            store = SessionPersistence(db_path=db_path)
            store.save_workspace_fingerprint("session-5", base_prefix_hash="abc123", rag_hash="def456")

            fp = store.get_workspace_fingerprint("session-5")

        assert fp is not None
        assert fp.get("base_prefix_hash") == "abc123"
        assert fp.get("rag_hash") == "def456"

    def test_cross_session_state_disabled_returns_none(self, tmp_path):
        """When cross_session_state.enabled=False, load_state should return None."""
        from mmcp.infrastructure.environment import config as config_module
        from mmcp.infrastructure.persistence.session_persistence import SessionPersistence

        mock_config = config_module.CLConfig()
        mock_config.cross_session_state_enabled = False

        with patch.object(config_module, "get_config", return_value=mock_config):
            store = SessionPersistence(db_path=tmp_path / "test_session.db")
            result = store.load_state("any-session")

        assert result is None