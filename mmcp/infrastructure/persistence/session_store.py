"""
SessionStore Facade ΓÇö Context-Life (CL)

Provides SQLite-backed persistence for cache metadata and usage telemetry.
Wires together 4 focused components:
- SessionStoreConnection: connection lifecycle
- SessionStoreMigrations: DDL versioning
- SessionStoreQueries: domain queries
- SessionStoreRowMapper: row-to-dict mapping

Keeps exact same public API as the original monolithic SessionStore
for backward compatibility.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from mmcp.domain.models import UsageEvent
from mmcp.infrastructure.environment.config import get_config
from mmcp.infrastructure.persistence.session_store_connection import SessionStoreConnection
from mmcp.infrastructure.persistence.session_store_migrations import SessionStoreMigrations
from mmcp.infrastructure.persistence.session_store_queries import SessionStoreQueries
from mmcp.infrastructure.persistence.session_store_row_mapper import SessionStoreRowMapper


class SessionStore:
    """SQLite-backed telemetry and cache store."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the store, creating the DB file and tables if missing."""
        if db_path is None:
            self.db_path: Path = get_config().resolve_cache_db_path()
        else:
            self.db_path = db_path

        # Wire the 4-component architecture
        self._connection = SessionStoreConnection(self.db_path)
        self._migrations = SessionStoreMigrations(self._connection)
        self._queries = SessionStoreQueries(self._connection)
        self._row_mapper = SessionStoreRowMapper()

        # Ensure DB exists and run migrations
        self._connection.ensure_connection()
        self._migrations.run_migrations()

    def lookup_prefix(self, content_hash: str) -> Optional[tuple[int, int]]:
        """Check if a prefix hash is in the durable cache."""
        return self._queries.lookup_prefix(content_hash)

    def record_prefix_hit(self, content_hash: str) -> None:
        """Increment the hit counter for an existing prefix."""
        return self._queries.record_prefix_hit(content_hash)

    def store_prefix(self, content_hash: str, token_count: int) -> None:
        """Store a new prefix hash with its token count."""
        return self._queries.store_prefix(content_hash, token_count)

    def evict_old_prefixes(self, max_entries: int) -> None:
        """Keep only the N most recent/hottest entries."""
        return self._queries.evict_old_prefixes(max_entries)

    def record_usage(self, event: UsageEvent) -> None:
        """Record a telemetry event to the usage ledger."""
        return self._queries.record_usage(event)

    def get_weekly_usage(self) -> dict[str, dict[str, int]]:
        """Returns weekly token stats grouped by model."""
        return self._queries.get_weekly_usage()

    def get_all_time_usage(self) -> dict[str, int]:
        """Returns total global usage across all time with explicit semantics."""
        return self._queries.get_all_time_usage()

    # Alias for backward compatibility
    def get_all_time_stats(self) -> dict[str, int]:
        """Returns total global usage across all time with explicit semantics."""
        return self.get_all_time_usage()

    def get_recent_stats(self, days: int = 7) -> dict[str, int]:
        """Return aggregate usage stats for a rolling N-day window."""
        window_start = time.time() - (days * 24 * 60 * 60)
        return self._queries._aggregate_usage_since(window_start)

    def clear(self) -> None:
        """Clear the entire database (mostly for testing)."""
        return self._connection.clear()

    # Additional methods from SessionStoreQueries
    def get_session_events(self, session_id: str) -> list[dict[str, Any]]:
        """Get all events for a specific session."""
        return self._queries.get_session_events(session_id)

    def get_active_sessions(self) -> list[dict[str, Any]]:
        """Get all sessions with recent activity."""
        return self._queries.get_active_sessions()

    def record_cache_hit(self, content_hash: str) -> None:
        """Record a cache hit."""
        return self._queries.record_cache_hit(content_hash)

    def record_cache_miss(self, content_hash: str, token_count: int) -> None:
        """Record a cache miss and store new entry."""
        return self._queries.record_cache_miss(content_hash, token_count)

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self._queries.get_cache_stats()

    def cleanup_expired_sessions(self, max_age_seconds: float) -> int:
        """Remove sessions older than max_age_seconds. Returns count removed."""
        return self._queries.cleanup_expired_sessions(max_age_seconds)


# Re-export all public names for backward compatibility
__all__ = [
    "SessionStore",
    "UsageEvent",
    "lookup_prefix",
    "record_usage",
    "get_weekly_usage",
    "get_all_time_usage",
    "get_all_time_stats",
    "get_session_events",
    "get_active_sessions",
    "record_cache_hit",
    "record_cache_miss",
    "get_cache_stats",
    "cleanup_expired_sessions",
    "record_prefix_hit",
    "store_prefix",
    "evict_old_prefixes",
    "clear",
    "get_recent_stats",
]