"""Port for SessionStore row-to-dict mapping operations."""

from __future__ import annotations

from typing import Any, Protocol

from mmcp.domain.models import UsageEvent


class SessionStoreRowMapperPort(Protocol):
    """Maps database rows to domain objects and dicts."""

    def map_row_to_usage_event(self, row: tuple) -> UsageEvent:
        """Convert a usage_events row to UsageEvent domain object."""
        ...

    def map_row_to_cache_entry(self, row: tuple) -> dict[str, Any]:
        """Convert a prefix_cache_entries row to dict."""
        ...

    def map_row_to_session(self, row: tuple) -> dict[str, Any]:
        """Convert a session row to dict."""
        ...

    def usage_event_to_dict(self, event: UsageEvent) -> dict[str, Any]:
        """Convert UsageEvent to dict for database insertion."""
        ...

    def cache_entry_to_dict(self, content_hash: str, token_count: int, hits: int) -> dict[str, Any]:
        """Create a cache entry dict."""
        ...

    def session_to_dict(self, session_id: str, event_count: int, last_timestamp: float) -> dict[str, Any]:
        """Create a session summary dict."""
        ...