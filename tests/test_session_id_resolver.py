"""
Tests for RFC-002 P5: Session ID Resolver.

Session ID derivation:
- IF ENGRAM_SESSION_ID env var → use directly
- ELSE IF .context-session.id exists AND < 12h old → read from file
- ELSE → compute hash(cwd + timestamp), save to .context-session.id, use it

TTL is 12 hours (43200 seconds).
DISABLE_AUTOINVOKE=1 → returns None (no-op).
"""

import hashlib
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from mmcp.infrastructure.session_id_resolver import resolve


class TestResolveSessionId:
    """Test session ID resolution paths."""

    def test_env_var_path(self):
        """ENGRAM_SESSION_ID env var → returns env var value."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"ENGRAM_SESSION_ID": "env-session-123"}, clear=False):
                result = resolve(cwd=tmp)

        assert result == "env-session-123"

    def test_file_read_path_valid(self):
        """.context-session.id exists and fresh → returns file content."""
        with tempfile.TemporaryDirectory() as tmp:
            session_file = Path(tmp) / ".context-session.id"
            session_file.write_text("file-session-456", encoding="utf-8")

            result = resolve(cwd=tmp)

        assert result == "file-session-456"

    def test_file_missing_new_hash_path(self):
        """File missing → compute hash, create file, return hash."""
        with tempfile.TemporaryDirectory() as tmp:
            session_file = Path(tmp) / ".context-session.id"
            assert not session_file.exists()

            result = resolve(cwd=tmp)

            # Should have created the file
            assert session_file.exists()
            # Should be a SHA256 hash (64 hex chars)
            assert len(result) == 64
            assert result == session_file.read_text(encoding="utf-8")

    def test_file_expired_ttl(self):
        """File exists but expired (>12h) → compute new hash, overwrite file."""
        with tempfile.TemporaryDirectory() as tmp:
            session_file = Path(tmp) / ".context-session.id"
            # Create old file (13 hours ago using mtime)
            old_time = time.time() - (13 * 3600)
            session_file.write_text("old-session-789", encoding="utf-8")
            os.utime(session_file, (old_time, old_time))

            result = resolve(cwd=tmp)

            # Should have overwritten with new hash
            new_content = session_file.read_text(encoding="utf-8")
            assert result == new_content
            assert new_content != "old-session-789"

    def test_disable_autoinvoke_returns_none(self):
        """DISABLE_AUTOINVOKE=1 → returns None (no-op)."""
        with tempfile.TemporaryDirectory() as tmp:
            session_file = Path(tmp) / ".context-session.id"
            session_file.write_text("should-not-read", encoding="utf-8")

            with patch.dict(os.environ, {"DISABLE_AUTOINVOKE": "1"}, clear=False):
                result = resolve(cwd=tmp)

        assert result is None
        # File should NOT have been created
        assert not session_file.exists() or session_file.read_text(encoding="utf-8") != "should-not-read"


class TestHashComputation:
    """Test hash computation for new session IDs."""

    def test_hash_is_sha256(self):
        """New session IDs should be valid SHA256 (64 hex chars)."""
        with tempfile.TemporaryDirectory() as tmp:
            result = resolve(cwd=tmp)

        # SHA256 produces 64 hex characters
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_changes_with_cwd(self):
        """Different cwd values should produce different hashes."""
        with tempfile.TemporaryDirectory() as tmp1:
            with tempfile.TemporaryDirectory() as tmp2:
                result1 = resolve(cwd=tmp1)
                result2 = resolve(cwd=tmp2)

        assert result1 != result2

    def test_hash_includes_timestamp(self):
        """Hash should include current timestamp (not deterministic)."""
        with tempfile.TemporaryDirectory() as tmp:
            session_file = Path(tmp) / ".context-session.id"
            # Remove file to force new hash
            if session_file.exists():
                session_file.unlink()

            result1 = resolve(cwd=tmp)

            # Wait a moment and compute again
            time.sleep(0.1)
            session_file.unlink()
            result2 = resolve(cwd=tmp)

        # Hashes should be different due to timestamp component
        # (this tests the algorithm includes time)
        assert result1 != result2