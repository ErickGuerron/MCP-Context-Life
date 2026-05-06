"""Port for SessionStore domain query operations."""

from __future__ import annotations

from typing import Any, Optional, Protocol

from mmcp.domain.models import UsageEvent


class SessionStoreQueriesPort(Protocol):
    """Handles all domain query operations for SessionStore."""

    def lookup_prefix(self, content_hash: str) -> Optional[tuple[int, int]]:
        """
        Check if a prefix hash is in the durable cache.
        Returns (token_count, hits) if found, else None.
        """
        ...

    def record_usage(self, event: UsageEvent) -> None:
        """Record a telemetry event to the usage ledger."""
        ...

    def get_weekly_usage(self) -> dict[str, dict[str, int]]:
        """Returns weekly token stats grouped by model."""
        ...

    def get_all_time_usage(self) -> dict[str, int]:
        """Returns total global usage across all time."""
        ...

    def get_session_events(self, session_id: str) -> list[dict[str, Any]]:
        """Get all events for a specific session."""
        ...

    def get_active_sessions(self) -> list[dict[str, Any]]:
        """Get all sessions with recent activity."""
        ...

    def record_cache_hit(self, content_hash: str) -> None:
        """Record a cache hit for a content hash."""
        ...

    def record_cache_miss(self, content_hash: str, token_count: int) -> None:
        """Record a cache miss and store new entry."""
        ...

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics including hits, misses, and entries."""
        ...

    def cleanup_expired_sessions(self, max_age_seconds: float) -> int:
        """Remove sessions older than max_age_seconds. Returns count removed."""
        ...