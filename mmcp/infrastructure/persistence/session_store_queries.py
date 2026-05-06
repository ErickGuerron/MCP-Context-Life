"""Domain query adapter for SessionStore."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from mmcp.application.ports.session_store_connection import SessionStoreConnectionPort
from mmcp.application.ports.session_store_queries import SessionStoreQueriesPort
from mmcp.domain.models import UsageEvent


class SessionStoreQueries(SessionStoreQueriesPort):
    """Handles all domain query operations for SessionStore."""

    def __init__(self, connection: SessionStoreConnectionPort):
        self._connection = connection

    @property
    def db_path(self) -> Optional[str]:
        """Expose db_path for backward compatibility (e.g., testing)."""
        if hasattr(self._connection, "db_path"):
            return str(self._connection.db_path)
        return None

    def lookup_prefix(self, content_hash: str) -> Optional[tuple[int, int]]:
        """
        Check if a prefix hash is in the durable cache.
        Returns (token_count, hits) if found, else None.
        """
        conn = self._connection.get_connection()
        try:
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
        finally:
            self._connection.close_connection(conn)

    def record_prefix_hit(self, content_hash: str) -> None:
        """Increment the hit counter for an existing prefix."""
        conn = self._connection.get_connection()
        try:
            conn.execute(
                """
                UPDATE prefix_cache_entries
                SET hits = hits + 1, last_hit = ?
                WHERE content_hash = ?
            """,
                (time.time(), content_hash),
            )
            conn.commit()
        finally:
            self._connection.close_connection(conn)

    def store_prefix(self, content_hash: str, token_count: int) -> None:
        """Store a new prefix hash with its token count."""
        conn = self._connection.get_connection()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO prefix_cache_entries (content_hash, token_count, created_at)
                VALUES (?, ?, ?)
            """,
                (content_hash, token_count, time.time()),
            )
            conn.commit()
        finally:
            self._connection.close_connection(conn)

    def evict_old_prefixes(self, max_entries: int) -> None:
        """Keep only the N most recent/hottest entries."""
        conn = self._connection.get_connection()
        try:
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
        finally:
            self._connection.close_connection(conn)

    def record_usage(self, event: UsageEvent) -> None:
        """Record a telemetry event to the usage ledger."""
        ts = event.timestamp or time.time()
        conn = self._connection.get_connection()
        try:
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
        finally:
            self._connection.close_connection(conn)

    def get_weekly_usage(self) -> dict[str, dict[str, int]]:
        """
        Returns weekly token stats grouped by model.
        """
        week_ago = time.time() - (7 * 24 * 60 * 60)
        conn = self._connection.get_connection()
        try:
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
        finally:
            self._connection.close_connection(conn)

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

        conn = self._connection.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
        finally:
            self._connection.close_connection(conn)

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

    def get_all_time_usage(self) -> dict[str, int]:
        """Returns total global usage across all time with explicit semantics."""
        return self._aggregate_usage_since()

    def get_session_events(self, session_id: str) -> list[dict[str, Any]]:
        """Get all events for a specific session."""
        conn = self._connection.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT timestamp, session_id, host_name, agent_name, provider_name,
                       model_name, input_tokens, output_tokens, cached_input_tokens,
                       uncached_input_tokens, effective_saved_tokens, tool_name, latency_ms
                FROM usage_events
                WHERE session_id = ?
                ORDER BY timestamp
            """,
                (session_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "timestamp": r[0],
                    "session_id": r[1],
                    "host_name": r[2],
                    "agent_name": r[3],
                    "provider_name": r[4],
                    "model_name": r[5],
                    "input_tokens": r[6],
                    "output_tokens": r[7],
                    "cached_input_tokens": r[8],
                    "uncached_input_tokens": r[9],
                    "effective_saved_tokens": r[10],
                    "tool_name": r[11],
                    "latency_ms": r[12],
                }
                for r in rows
            ]
        finally:
            self._connection.close_connection(conn)

    def get_active_sessions(self) -> list[dict[str, Any]]:
        """Get all sessions with recent activity."""
        conn = self._connection.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT session_id, COUNT(*) as event_count, MAX(timestamp) as last_timestamp
                FROM usage_events
                GROUP BY session_id
                ORDER BY last_timestamp DESC
            """
            )
            rows = cursor.fetchall()
            return [
                {
                    "session_id": r[0],
                    "event_count": r[1],
                    "last_timestamp": r[2],
                }
                for r in rows
            ]
        finally:
            self._connection.close_connection(conn)

    def record_cache_hit(self, content_hash: str) -> None:
        """Record a cache hit by incrementing the hit counter."""
        self.record_prefix_hit(content_hash)

    def record_cache_miss(self, content_hash: str, token_count: int) -> None:
        """Record a cache miss and store new entry."""
        self.store_prefix(content_hash, token_count)

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics including hits, misses, and entries."""
        conn = self._connection.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), SUM(hits) FROM prefix_cache_entries")
            row = cursor.fetchone()
            total_entries = row[0] or 0
            total_hits = row[1] or 0
            return {
                "total_entries": total_entries,
                "total_hits": total_hits,
            }
        finally:
            self._connection.close_connection(conn)

    def cleanup_expired_sessions(self, max_age_seconds: float) -> int:
        """Remove sessions older than max_age_seconds. Returns count removed."""
        cutoff = time.time() - max_age_seconds
        conn = self._connection.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM usage_events WHERE timestamp < ?", (cutoff,))
            conn.commit()
            return cursor.rowcount
        finally:
            self._connection.close_connection(conn)