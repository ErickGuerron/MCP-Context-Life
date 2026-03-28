"""
Cache Manager Module — Context-Life (CL)

Implements context caching strategies to leverage provider-level
prompt caching (Anthropic, Google Gemini, OpenAI).

The idea: if the static prefix of your messages (system prompt + RAG context)
hasn't changed between turns, the LLM provider can serve it from cache,
saving up to 90% on input tokens for that portion.

Components:
  - CacheStore: Tracks content hashes to detect prefix stability
  - CacheLoop: Orchestrates cache-aware message construction

RFC Improvements Applied:
  - P1: Real tiktoken counting instead of len//4 estimates
  - P2: Internal metadata (_mmcp_cache_control) stripped from messages,
         returned as separate metadata only
  - P5: Canonical hash — normalizes whitespace/key order for stable hashing
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from mmcp.token_counter import count_tokens, DEFAULT_ENCODING


def _canonicalize_content(content: str) -> str:
    """
    P5: Canonical normalization before hashing.

    Strips irrelevant differences that don't affect semantics:
      - Trailing/leading whitespace per line
      - Multiple consecutive blank lines → single blank line
      - Trailing whitespace at end of content

    This prevents cache misses from minor formatting changes
    while preserving meaningful content differences.
    """
    # Normalize line endings
    content = content.replace("\r\n", "\n")
    # Strip trailing whitespace per line
    lines = [line.rstrip() for line in content.split("\n")]
    # Collapse multiple blank lines into one
    normalized: list[str] = []
    prev_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        normalized.append(line)
        prev_blank = is_blank
    return "\n".join(normalized).strip()


def _hash_content(content: str) -> str:
    """
    P5: Hash with canonical normalization.
    Fast SHA-256 hash for content comparison.
    """
    canonical = _canonicalize_content(content)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


@dataclass
class CacheEntry:
    """A cached prefix entry with metadata."""

    content_hash: str
    token_count: int
    created_at: float = field(default_factory=time.time)
    hits: int = 0
    last_hit: Optional[float] = None

    def record_hit(self) -> None:
        self.hits += 1
        self.last_hit = time.time()


@dataclass
class CacheStats:
    """Aggregated cache performance metrics."""

    total_lookups: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    tokens_saved: int = 0  # P1: Real count, not estimate

    @property
    def hit_rate(self) -> float:
        if self.total_lookups == 0:
            return 0.0
        return round((self.cache_hits / self.total_lookups) * 100, 2)

    def to_dict(self) -> dict:
        return {
            "total_lookups": self.total_lookups,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate_percent": self.hit_rate,
            "tokens_saved": self.tokens_saved,
        }


class CacheStore:
    """
    In-memory store that tracks content hashes to detect
    when the static prefix (system + RAG context) hasn't changed.

    This enables the MCP to signal to clients that the prefix
    is cache-eligible, allowing providers like Anthropic/Google
    to serve it from their prompt cache.
    """

    def __init__(self, max_entries: int = 100):
        self._entries: dict[str, CacheEntry] = {}
        self._max_entries = max_entries
        self.stats = CacheStats()

    def lookup(self, content: str) -> tuple[bool, str]:
        """
        Check if content is already cached.

        Returns:
            (is_cached, content_hash)
        """
        content_hash = _hash_content(content)
        self.stats.total_lookups += 1

        if content_hash in self._entries:
            self._entries[content_hash].record_hit()
            self.stats.cache_hits += 1
            return True, content_hash

        self.stats.cache_misses += 1
        return False, content_hash

    def store(self, content: str, token_count: int) -> str:
        """
        Store a content hash in the cache.

        Returns the content hash for tracking.
        """
        content_hash = _hash_content(content)

        # Evict oldest if at capacity
        if len(self._entries) >= self._max_entries and content_hash not in self._entries:
            oldest_key = min(self._entries, key=lambda k: self._entries[k].created_at)
            del self._entries[oldest_key]

        self._entries[content_hash] = CacheEntry(
            content_hash=content_hash,
            token_count=token_count,
        )
        return content_hash

    def get_token_count(self, content_hash: str) -> int:
        """Get the stored token count for a hash."""
        entry = self._entries.get(content_hash)
        return entry.token_count if entry else 0

    def get_stats(self) -> dict:
        """Get cache performance statistics."""
        return self.stats.to_dict()

    def clear(self) -> None:
        """Clear all cache entries and reset stats."""
        self._entries.clear()
        self.stats = CacheStats()


class CacheLoop:
    """
    Orchestrates cache-aware message construction.

    The Cache Loop ensures that the static portion of the context
    (system prompts, RAG-injected knowledge) is grouped and stabilized
    at the TOP of the message array. This maximizes prompt cache hits
    because providers cache based on prefix matching.

    Flow:
      1. Separate messages into static (system/rag) and dynamic (user/assistant)
      2. Hash the static portion (P5: with canonical normalization)
      3. If hash matches previous turn → prefix is cacheable
      4. Return CLEAN messages (P2: no internal metadata)
         with cache info as SEPARATE metadata
    """

    def __init__(self, encoding: str = DEFAULT_ENCODING):
        self._store = CacheStore()
        self._last_static_hash: Optional[str] = None
        self._encoding = encoding

    def process_messages(
        self,
        messages: list[dict],
        rag_context: Optional[str] = None,
    ) -> dict:
        """
        Process a message array for cache optimization.

        Separates static prefix from dynamic conversation,
        checks cache status, and returns result.

        P1: Uses real tiktoken counting for accurate metrics.
        P2: Messages are returned CLEAN — no _mmcp_cache_control injected.
            Cache info is in the separate 'cache_metadata' field.
        P5: Static prefix is canonicalized before hashing.

        Args:
            messages: Full message array
            rag_context: Optional RAG context to inject as static prefix

        Returns:
            Dict with clean messages, cache metadata, and stats
        """
        # Phase 1: Separate static from dynamic
        static_messages: list[dict] = []
        dynamic_messages: list[dict] = []

        for msg in messages:
            role = msg.get("role", "").lower()
            if role in ("system", "developer"):
                static_messages.append(msg)
            else:
                dynamic_messages.append(msg)

        # Phase 2: Inject RAG context into static prefix if provided
        if rag_context:
            rag_message = {
                "role": "system",
                "content": f"[CL Knowledge Context]\n{rag_context}",
            }
            static_messages.append(rag_message)

        # Phase 3: P1 — Count static prefix tokens with REAL tiktoken
        static_content = json.dumps(static_messages, sort_keys=True)
        static_token_count = count_tokens(static_content, self._encoding)

        # Phase 4: P5 — Hash with canonical normalization
        is_cached, content_hash = self._store.lookup(static_content)

        if not is_cached:
            self._store.store(static_content, static_token_count)

        # Phase 5: Detect cache hit (same prefix as last turn)
        cache_hit = content_hash == self._last_static_hash
        self._last_static_hash = content_hash

        # P1: Real token savings tracking
        if cache_hit:
            self._store.stats.tokens_saved += static_token_count

        # Phase 6: P2 — Return CLEAN messages, NO internal metadata injected
        # Cache info stays in the separate 'cache_metadata' field
        optimized_messages = static_messages + dynamic_messages

        # Count total tokens for the full optimized payload
        total_token_count = count_tokens(
            json.dumps(optimized_messages, sort_keys=True), self._encoding
        )

        return {
            "messages": optimized_messages,
            "cache_metadata": {
                "static_prefix_hash": content_hash,
                "is_cache_hit": cache_hit,
                "cache_eligible": True,
                "static_messages_count": len(static_messages),
                "dynamic_messages_count": len(dynamic_messages),
                "static_prefix_tokens": static_token_count,
                "total_tokens": total_token_count,
            },
            "stats": self._store.get_stats(),
        }

    def get_stats(self) -> dict:
        """Get cache performance statistics."""
        return self._store.get_stats()

    def reset(self) -> None:
        """Reset cache state."""
        self._store.clear()
        self._last_static_hash = None
