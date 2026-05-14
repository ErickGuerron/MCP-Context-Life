"""
Cross-Session Persistence - Context-Life (CL)

Phase 6 of mcp-context-life-auto-invocation-improvements SDD.

Provides cross-session state persistence using SQLite with:
- Two tables: session_state (current) + session_journal (append-only for replay)
- Atomic writes via SQLite transactions
- journal_replay() on startup to reconstruct state from journal
- Corrupted state archive + fresh start fallback
- Workspace fingerprint persistence (base_prefix_hash, RAG hash)
- Memory-only mode when cross_session_state.enabled=False
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional


class SessionPersistence:
    """
    SQLite-backed cross-session state persistence.

    Uses two tables:
      - session_state: current state (key-value per session)
      - session_journal: append-only log for replay/reconstruction

    On init, replays journal to reconstruct state from last known good state.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize persistence store, creating tables and replaying journal."""
        self._enabled = True

        # Check feature flag - import each time to allow patching
        try:
            from mmcp.infrastructure.environment.config import get_config
            cfg = get_config()
            self._enabled = cfg.cross_session_state_enabled
        except Exception:
            self._enabled = False

        # Resolve db path
        if db_path is None:
            from mmcp.infrastructure.environment.config import get_config
            cfg = get_config()
            self._db_path: Path = cfg.resolve_cache_db_path()
        else:
            self._db_path = db_path

        # Archive path for corrupted states
        self._archive_dir = self._db_path.parent / "state_archive"
        self._archive_dir.mkdir(parents=True, exist_ok=True)

        if self._enabled:
            self._ensure_tables()
            self._journal_replay()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a SQLite connection."""
        return sqlite3.connect(str(self._db_path), check_same_thread=False)

    def _ensure_tables(self) -> None:
        """Create tables if they don't exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Current state table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_state (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    base_prefix_hash TEXT,
                    rag_hash TEXT
                )
            """)

            # Append-only journal for replay
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    archived INTEGER DEFAULT 0
                )
            """)

            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_session ON session_journal(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_state_session ON session_state(session_id)")

            conn.commit()
        finally:
            conn.close()

    def _journal_replay(self) -> None:
        """
        Replay journal on startup to reconstruct state.

        For each session, find the last non-archived journal entry
        and update session_state from it. Corrupted entries are archived.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Find the last good entry per session from journal
            cursor.execute("""
                SELECT id, session_id, state_json, timestamp
                FROM session_journal
                WHERE archived = 0
                  AND id IN (
                      SELECT MAX(id)
                      FROM session_journal
                      WHERE archived = 0
                      GROUP BY session_id
                  )
            """)

            for row in cursor.fetchall():
                entry_id, session_id, state_json, timestamp = row
                try:
                    json.loads(state_json)
                    # Upsert into session_state
                    cursor.execute("""
                        INSERT OR REPLACE INTO session_state (session_id, state_json, updated_at)
                        VALUES (?, ?, ?)
                    """, (session_id, state_json, timestamp))
                    # Mark journal entry as replayed (not archived, but state now in session_state)
                except (json.JSONDecodeError, TypeError):
                    # Archive corrupted journal entry
                    cursor.execute("""
                        UPDATE session_journal SET archived = 1 WHERE id = ?
                    """, (entry_id,))

            conn.commit()
        finally:
            conn.close()

    def save_state(self, session_id: str, state: dict[str, Any]) -> None:
        """
        Save state atomically. Writes to journal first, then updates state table.

        If cross_session_state.enabled=False, this is a no-op.
        Raises TypeError if state is not a dict.
        """
        if not self._enabled:
            return

        if not isinstance(state, dict):
            raise TypeError(f"state must be a dict, got {type(state).__name__}")

        ts = time.time()
        state_json = json.dumps(state, sort_keys=True)

        conn = self._get_connection()
        try:
            # Check for corruption before writing
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT state_json FROM session_state WHERE session_id = ?", (session_id,))
                row = cursor.fetchone()
                if row:
                    json.loads(row[0])  # validate prior state
            except (json.JSONDecodeError, TypeError):
                # Prior state corrupted - archive it
                self._archive_session(session_id)
            except Exception:
                pass

            # Atomic write: journal first, then state table
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            try:
                # Append to journal
                cursor.execute("""
                    INSERT INTO session_journal (session_id, state_json, timestamp, archived)
                    VALUES (?, ?, ?, 0)
                """, (session_id, state_json, ts))

                # Update current state
                cursor.execute("""
                    INSERT OR REPLACE INTO session_state (session_id, state_json, updated_at)
                    VALUES (?, ?, ?)
                """, (session_id, state_json, ts))

                conn.commit()
            except Exception:
                conn.rollback()
                raise
        finally:
            conn.close()

    def load_state(self, session_id: str) -> Optional[dict[str, Any]]:
        """
        Load state for session_id. Returns None if not found or if
        cross_session_state.enabled=False (memory-only mode).

        If corrupted, archives and returns None (fresh start).
        """
        if not self._enabled:
            return None

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT state_json FROM session_state WHERE session_id = ?
            """, (session_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            try:
                state = json.loads(row[0])
                return state
            except (json.JSONDecodeError, TypeError):
                # Corrupted - archive and fresh start
                self._archive_session(session_id)
                return None
        finally:
            conn.close()

    def save_workspace_fingerprint(
        self, session_id: str, base_prefix_hash: str, rag_hash: str
    ) -> None:
        """Persist workspace fingerprint (base prefix hash, RAG hash) for session."""
        if not self._enabled:
            return

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Upsert fingerprint into session_state
            cursor.execute("""
                INSERT INTO session_state (session_id, state_json, updated_at, base_prefix_hash, rag_hash)
                VALUES (?, '{}', ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    base_prefix_hash = excluded.base_prefix_hash,
                    rag_hash = excluded.rag_hash,
                    updated_at = excluded.updated_at
            """, (session_id, time.time(), base_prefix_hash, rag_hash))
            conn.commit()
        finally:
            conn.close()

    def get_workspace_fingerprint(self, session_id: str) -> Optional[dict[str, str]]:
        """Get workspace fingerprint for session_id."""
        if not self._enabled:
            return None

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT base_prefix_hash, rag_hash FROM session_state
                WHERE session_id = ? AND (base_prefix_hash IS NOT NULL OR rag_hash IS NOT NULL)
            """, (session_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "base_prefix_hash": row[0] if row[0] else None,
                    "rag_hash": row[1] if row[1] else None,
                }
            return None
        finally:
            conn.close()

    def _archive_session(self, session_id: str) -> None:
        """Archive corrupted session state to archive directory."""
        ts = time.time()
        archive_file = self._archive_dir / f"{session_id}_{ts}.corrupted.json"

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Get corrupted data before deleting
            cursor.execute("SELECT state_json FROM session_state WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                try:
                    archive_file.write_text(row[0])
                except Exception:
                    pass  # best effort archive

            # Delete corrupted state
            cursor.execute("DELETE FROM session_state WHERE session_id = ?", (session_id,))
            # Mark journal entries as archived
            cursor.execute("UPDATE session_journal SET archived = 1 WHERE session_id = ?", (session_id,))
            conn.commit()
        finally:
            conn.close()

    def clear(self, session_id: str) -> None:
        """Clear state for a session (both state and journal entries)."""
        if not self._enabled:
            return

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM session_state WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM session_journal WHERE session_id = ?", (session_id,))
            conn.commit()
        finally:
            conn.close()
