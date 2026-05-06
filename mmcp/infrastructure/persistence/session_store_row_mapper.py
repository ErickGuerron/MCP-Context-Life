"""Row mapping adapter for SessionStore."""

from __future__ import annotations

from typing import Any

from mmcp.application.ports.session_store_row_mapper import SessionStoreRowMapperPort
from mmcp.domain.models import UsageEvent


class SessionStoreRowMapper(SessionStoreRowMapperPort):
    """Maps database rows to domain objects and dicts."""

    def map_row_to_usage_event(self, row: tuple) -> UsageEvent:
        """Convert a usage_events row to UsageEvent domain object."""
        return UsageEvent(
            session_id=row[1],  # session_id
            timestamp=row[0],  # timestamp
            host_name=row[2] or "unknown",
            agent_name=row[3] or "unknown",
            provider_name=row[4] or "unknown",
            model_name=row[5] or "unknown",
            input_tokens=row[6] or 0,
            output_tokens=row[7] or 0,
            cached_input_tokens=row[8] or 0,
            uncached_input_tokens=row[9] or 0,
            effective_saved_tokens=row[10] or 0,
            tool_name=row[11] or "unknown",
            latency_ms=row[12] or 0.0,
        )

    def map_row_to_cache_entry(self, row: tuple) -> dict[str, Any]:
        """Convert a prefix_cache_entries row to dict."""
        return {
            "content_hash": row[0],  # content_hash
            "token_count": row[1],  # token_count
            "hits": row[2],  # hits
            "created_at": row[3],  # created_at
            "last_hit": row[4],  # last_hit
        }

    def map_row_to_session(self, row: tuple) -> dict[str, Any]:
        """Convert a session row to dict."""
        return {
            "session_id": row[0],
            "event_count": row[1],
            "last_timestamp": row[2],
        }

    def usage_event_to_dict(self, event: UsageEvent) -> dict[str, Any]:
        """Convert UsageEvent to dict for database insertion values."""
        return {
            "timestamp": event.timestamp,
            "session_id": event.session_id,
            "host_name": event.host_name,
            "agent_name": event.agent_name,
            "provider_name": event.provider_name,
            "model_name": event.model_name,
            "input_tokens": event.input_tokens,
            "output_tokens": event.output_tokens,
            "cached_input_tokens": event.cached_input_tokens,
            "uncached_input_tokens": event.uncached_input_tokens,
            "effective_saved_tokens": event.effective_saved_tokens,
            "tool_name": event.tool_name,
            "latency_ms": event.latency_ms,
        }

    def cache_entry_to_dict(self, content_hash: str, token_count: int, hits: int) -> dict[str, Any]:
        """Create a cache entry dict."""
        return {
            "content_hash": content_hash,
            "token_count": token_count,
            "hits": hits,
        }

    def session_to_dict(self, session_id: str, event_count: int, last_timestamp: float) -> dict[str, Any]:
        """Create a session summary dict."""
        return {
            "session_id": session_id,
            "event_count": event_count,
            "last_timestamp": last_timestamp,
        }