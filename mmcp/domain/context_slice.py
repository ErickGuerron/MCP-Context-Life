"""
ContextSlice — enriched context wrapper with cache metadata for auto-invoke optimization.

Extends the context slice to carry:
- cache_key: SHA-256 hash of the operation signature
- cache_hit: boolean indicating if this was a cache hit
- ttl_seconds: remaining TTL if cached
- latency_ms: execution time
- lazy module loading support for heavy modules

This enables sub-agents to make informed decisions based on cache state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional


@dataclass
class ContextSlice:
    """
    Enriched context slice with cache metadata for auto-invoke optimization.

    Attributes:
        messages: The message array (trimmed or original)
        cache_key: SHA-256 hash of the operation signature (host/agent/provider/model/operation/args)
        cache_hit: Whether this result was served from cache
        ttl_seconds: Remaining TTL if cached (0 if not cached or expired)
        latency_ms: Execution time in milliseconds
        lazy_loader: Optional callable to lazily load heavy modules on cache miss
    """

    messages: List[dict]
    cache_key: Optional[str] = None
    cache_hit: bool = False
    ttl_seconds: int = 0
    latency_ms: float = 0.0
    lazy_loader: Optional[Callable[[], None]] = field(default=None, repr=False)

    def with_cache_metadata(
        messages: List[dict],
        cache_key: str,
        cache_hit: bool,
        ttl_seconds: int,
        latency_ms: float,
    ) -> ContextSlice:
        """
        Create a ContextSlice with cache metadata.

        Args:
            messages: The message array
            cache_key: SHA-256 key from the auto-invoke cache
            cache_hit: True if served from cache, False otherwise
            ttl_seconds: Remaining TTL (0 if not cached)
            latency_ms: Execution latency in ms

        Returns:
            ContextSlice with all cache metadata fields populated
        """
        return ContextSlice(
            messages=messages,
            cache_key=cache_key,
            cache_hit=cache_hit,
            ttl_seconds=ttl_seconds,
            latency_ms=latency_ms,
        )

    @staticmethod
    def set_lazy_loader(loader: Callable[[], None]) -> None:
        """
        Set the lazy module loader for heavy modules.

        When cache misses occur and heavy modules (RAG, embeddings) are needed,
        this loader is called to initialize them. Subsequent cache hits bypass
        the loading entirely.

        Args:
            loader: Callable that initializes the heavy module(s)
        """
        # This would be stored in a module-level variable or dependency injection
        # For now, just a placeholder that documents the intent
        pass

    @staticmethod
    def clear_lazy_loader() -> None:
        """Clear the lazy module loader."""
        pass

    def to_dict(self) -> dict:
        """Convert to dictionary representation for MCP responses."""
        return {
            "messages": self.messages,
            "cache_metadata": {
                "cache_key": self.cache_key,
                "cache_hit": self.cache_hit,
                "ttl_seconds": self.ttl_seconds,
                "latency_ms": self.latency_ms,
            },
        }

    @property
    def tokens_saved(self) -> int:
        """
        Estimate tokens saved by cache hit.

        Returns 0 if not a cache hit, otherwise estimates based on typical
        cache hit savings (avoiding re-computation of RAG, embeddings, etc.)
        """
        if not self.cache_hit:
            return 0
        # Typical cache hit saves re-computation of:
        # - RAG embedding: ~500-1000 tokens equivalent
        # - Token counting: ~100 tokens equivalent
        return 600  # Conservative estimate

    @property
    def is_cache_warm(self) -> bool:
        """Return True if cache is warm (recent hit)."""
        return self.cache_hit and self.ttl_seconds > 0


# Module-level lazy loader (internal)
_lazy_loader: Optional[Callable[[], None]] = None


def _get_lazy_loader() -> Optional[Callable[[], None]]:
    """Get the current lazy loader."""
    return _lazy_loader


def _set_lazy_loader(loader: Callable[[], None]) -> None:
    """Set the lazy loader."""
    global _lazy_loader
    _lazy_loader = loader


def _clear_lazy_loader() -> None:
    """Clear the lazy loader."""
    global _lazy_loader
    _lazy_loader = None


def invoke_lazy_loader() -> None:
    """Invoke the lazy loader if set."""
    loader = _get_lazy_loader()
    if loader is not None:
        loader()