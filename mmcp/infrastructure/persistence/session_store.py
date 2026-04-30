"""
Session Store Module ΓÇö Context-Life (CL)

Provides SQLite-backed persistence for cache metadata and usage telemetry.
Ensures base prefix hashes survive process restarts, exposing real savings
early in user workflows according to the RFC Phase 1 & 2.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mmcp.infrastructure.environment.config import get_config


@dataclass
class UsageEvent:
    """Normalized usage telemetry event."""

    session_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    uncached_input_tokens: int = 0
    effective_saved_tokens: int = 0
    host_name: str = "unknown"
    agent_name: str = "unknown"
    provider_name: str = "unknown"
    model_name: str = "unknown"
    tool_name: str = "unknown"
    latency_ms: float = 0.0
    timestamp: float = 0.0


class SessionStore:
    """SQLite-backed telemetry and cache store."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the store, creating the DB file and tables if missing."""
        if db_path is None:
            self.db_path = get_config().resolve_cache_db_path()
        else:
            self.db_path = db_path

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Phase 2: Prefix Cache Ledger (no sensitive prompt payload)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prefix_cache_entries (
                    content_hash TEXT PRIMARY KEY,
                    token_count INTEGER NOT NULL,
                    hits INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    last_hit REAL
                )
            """)

            # Phase 1: Usage Ledger
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    session_id TEXT NOT NULL,
                    host_name TEXT,
                    agent_name TEXT,
                    provider_name TEXT,
                    model_name TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    cached_input_tokens INTEGER,
                    uncached_input_tokens INTEGER,
                    effective_saved_tokens INTEGER,
                    tool_name TEXT,
                    latency_ms REAL
                )
            """)

            # Indexes for faster TUI querying later
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_created ON prefix_cache_entries(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_session ON usage_events(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_host ON usage_events(host_name)")

            conn.commit()

    def lookup_prefix(self, content_hash: str) -> Optional[tuple[int, int]]:
        """
        Check if a prefix hash is in the durable cache.
        Returns (token_count, hits) if found, else None.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT token_count, hits FROM prefix_cache_entries
                WHERE content_hash = ?
            """,
                (content_hash,),
            )
            row = cursor.fetchone()
            return row

    def record_prefix_hit(self, content_hash: str) -> None:
        """Increment the hit counter for an existing prefix."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE prefix_cache_entries
                SET hits = hits + 1, last_hit = ?
                WHERE content_hash = ?
            """,
                (time.time(), content_hash),
            )
            conn.commit()

    def store_prefix(self, content_hash: str, token_count: int) -> None:
        """Store a new prefix hash with its token count."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO prefix_cache_entries (content_hash, token_count, created_at)
                VALUES (?, ?, ?)
            """,
                (content_hash, token_count, time.time()),
            )
            conn.commit()

    def evict_old_prefixes(self, max_entries: int) -> None:
        """Keep only the N most recent/hottest entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                DELETE FROM prefix_cache_entries
                WHERE content_hash NOT IN (
                    SELECT content_hash FROM prefix_cache_entries
                    ORDER BY last_hit DESC, created_at DESC
                    LIMIT ?
                )
            """,
                (max_entries,),
            )
            conn.commit()

    def record_usage(self, event: UsageEvent) -> None:
        """Record a telemetry event to the usage ledger."""
        ts = event.timestamp or time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO usage_events (
                    timestamp, session_id, host_name, agent_name, provider_name, model_name,
                    input_tokens, output_tokens, cached_input_tokens, uncached_input_tokens,
                    effective_saved_tokens, tool_name, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    ts,
                    event.session_id,
                    event.host_name,
                    event.agent_name,
                    event.provider_name,
                    event.model_name,
                    event.input_tokens,
                    event.output_tokens,
                    event.cached_input_tokens,
                    event.uncached_input_tokens,
                    event.effective_saved_tokens,
                    event.tool_name,
                    event.latency_ms,
                ),
            )
            conn.commit()

    def clear(self) -> None:
        """Clear the entire database (mostly for testing)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM prefix_cache_entries")
            conn.execute("DELETE FROM usage_events")
            conn.commit()

    def _aggregate_usage_since(self, since_timestamp: float | None = None) -> dict[str, int]:
        """Aggregate explicit usage counters, optionally bounded by a start timestamp."""
        query = """
            SELECT
                SUM(input_tokens),
                SUM(output_tokens),
                SUM(effective_saved_tokens),
                SUM(cached_input_tokens),
                SUM(uncached_input_tokens)
            FROM usage_events
        """
        params: tuple[float, ...] = ()
        if since_timestamp is not None:
            query += " WHERE timestamp >= ?"
            params = (since_timestamp,)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()

        accounted_input_tokens = row[0] or 0
        output_tokens = row[1] or 0
        saved_tokens = row[2] or 0
        cached_input_tokens = row[3] or 0
        live_input_tokens = row[4] or 0
        activity_tokens = accounted_input_tokens + output_tokens
        return {
            "accounted_input_tokens": accounted_input_tokens,
            "output_tokens": output_tokens,
            "saved_tokens": saved_tokens,
            "cached_input_tokens": cached_input_tokens,
            "live_input_tokens": live_input_tokens,
            "activity_tokens": activity_tokens,
            "used": activity_tokens,
            "saved": saved_tokens,
        }

    def get_weekly_usage(self) -> dict[str, dict[str, int]]:
        """
        Returns weekly token stats grouped by model.

        New explicit fields clarify semantics:
        - accounted_input_tokens: request/context tokens examined by the tool
        - output_tokens: transformed/generated tokens returned by the tool
        - saved_tokens: cache/trim savings attributed to the tool

        Legacy aliases remain for compatibility:
        - used = activity_tokens
        - saved = saved_tokens
        """
        week_ago = time.time() - (7 * 24 * 60 * 60)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    model_name,
                    SUM(input_tokens) as total_input,
                    SUM(output_tokens) as total_output,
                    SUM(effective_saved_tokens) as total_saved,
                    SUM(cached_input_tokens) as total_cached_input,
                    SUM(uncached_input_tokens) as total_uncached_input
                FROM usage_events
                WHERE timestamp >= ?
                GROUP BY model_name
            """,
                (week_ago,),
            )

            results = {}
            for row in cursor.fetchall():
                model = row[0] or "unknown"
                accounted_input_tokens = row[1] or 0
                output_tokens = row[2] or 0
                saved_tokens = row[3] or 0
                cached_input_tokens = row[4] or 0
                live_input_tokens = row[5] or 0
                activity_tokens = accounted_input_tokens + output_tokens
                results[model] = {
                    "accounted_input_tokens": accounted_input_tokens,
                    "output_tokens": output_tokens,
                    "saved_tokens": saved_tokens,
                    "cached_input_tokens": cached_input_tokens,
                    "live_input_tokens": live_input_tokens,
                    "activity_tokens": activity_tokens,
                    "used": activity_tokens,
                    "saved": saved_tokens,
                }
            return results

    def get_recent_stats(self, days: int = 7) -> dict[str, int]:
        """Return aggregate usage stats for a rolling N-day window."""
        window_start = time.time() - (days * 24 * 60 * 60)
        return self._aggregate_usage_since(window_start)

    def get_all_time_stats(self) -> dict[str, int]:
        """Returns total global usage across all time with explicit semantics."""
        return self._aggregate_usage_since()
