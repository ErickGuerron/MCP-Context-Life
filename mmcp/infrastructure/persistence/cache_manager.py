"""
Cache Manager Module ΓÇö Context-Life (CL)

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
  - P5: Canonical hash ΓÇö normalizes whitespace/key order for stable hashing
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional

from mmcp.application.ports.session_store import PrefixCacheStorePort
from mmcp.infrastructure.environment.config import get_config
from mmcp.infrastructure.environment.orchestrator_detector import get_orchestrator_info
from mmcp.infrastructure.persistence.session_store import SessionStore
from mmcp.infrastructure.tokens.token_counter import DEFAULT_ENCODING, count_tokens


def _canonicalize_content(content: str) -> str:
    """
    P5: Canonical normalization before hashing.

    Strips irrelevant differences that don't affect semantics:
      - Trailing/leading whitespace per line
      - Multiple consecutive blank lines ΓåÆ single blank line
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

    def __init__(self, max_entries: Optional[int] = None, session_store: Optional[PrefixCacheStorePort] = None):
        self._max_entries = max_entries or get_config().cache_max_entries
        self._entries: dict[str, CacheEntry] = {}
        self._session_store = session_store or SessionStore()
        self.stats = CacheStats()

    def lookup(self, content: str) -> tuple[bool, str]:
        """
        Check if content is already cached (L1 memory or L2 SQLite).

        Returns:
            (is_cached, content_hash)
        """
        content_hash = _hash_content(content)
        self.stats.total_lookups += 1

        # L1 check
        if content_hash in self._entries:
            self._entries[content_hash].record_hit()
            self._session_store.record_prefix_hit(content_hash)
            self.stats.cache_hits += 1
            return True, content_hash

        # L2 check (SQLite)
        row = self._session_store.lookup_prefix(content_hash)
        if row:
            token_count, sq_hits = row
            # Promote to L1
            entry = CacheEntry(
                content_hash=content_hash,
                token_count=token_count,
            )
            entry.hits = sq_hits
            entry.record_hit()
            self._entries[content_hash] = entry
            self._session_store.record_prefix_hit(content_hash)

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

        # L2 write-through
        self._session_store.store_prefix(content_hash, token_count)
        self._session_store.evict_old_prefixes(self._max_entries)

        return content_hash

    def get_token_count(self, content_hash: str) -> int:
        """Get the stored token count for a hash."""
        entry = self._entries.get(content_hash)
        return entry.token_count if entry else 0

    def get_stats(self) -> dict:
        """Get cache performance statistics."""
        return self.stats.to_dict()

    def clear(self) -> None:
        """Clear L1 cache entries and stats (keeps L2 persistent)."""
        self._entries.clear()
        self.stats = CacheStats()

    def hard_clear(self) -> None:
        """Clear L1 AND wipe persistent L2 storage."""
        self.clear()
        self._session_store.clear()


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
      3. If hash matches previous turn ΓåÆ prefix is cacheable
      4. Return CLEAN messages (P2: no internal metadata)
         with cache info as SEPARATE metadata
    """

    def __init__(self, encoding: str = DEFAULT_ENCODING):
        config = get_config()
        self._store = CacheStore()
        self._last_static_hash: Optional[str] = None
        self._last_base_hash: Optional[str] = None
        self._last_rag_hash: Optional[str] = None
        self._rag_change_streak: int = 0
        self._rag_bypass_remaining: int = 0
        self._rag_thrash_threshold = max(1, config.cache_rag_thrash_threshold)
        self._rag_bypass_cooldown = max(1, config.cache_rag_bypass_cooldown)
        self._encoding = encoding

    def _update_rag_stability(self, rag_hash: Optional[str]) -> dict:
        """Track repeated RAG churn and expose a controlled bypass hint."""
        bypass_active = False
        trigger = False

        if rag_hash is None:
            self._rag_change_streak = 0
            self._rag_bypass_remaining = 0
        else:
            if self._last_rag_hash and rag_hash != self._last_rag_hash:
                self._rag_change_streak += 1
            else:
                self._rag_change_streak = 0

            if self._rag_change_streak >= self._rag_thrash_threshold:
                self._rag_bypass_remaining = self._rag_bypass_cooldown
                trigger = True

            if self._rag_bypass_remaining > 0:
                bypass_active = True
                self._rag_bypass_remaining -= 1

        self._last_rag_hash = rag_hash
        return {
            "bypass_active": bypass_active,
            "triggered": trigger,
            "change_streak": self._rag_change_streak,
        }

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
        P2: Messages are returned CLEAN ΓÇö no _mmcp_cache_control injected.
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

        # Phase 2: Build base prefix (system/developer only ΓÇö NO RAG)
        base_content = json.dumps(static_messages, sort_keys=True)
        base_token_count = count_tokens(base_content, self._encoding)
        _, base_hash = self._store.lookup(base_content)

        # Phase 3: Inject RAG context if provided
        rag_hash = None
        rag_token_count = 0
        if rag_context:
            rag_message = {
                "role": "system",
                "content": f"[CL Knowledge Context]\n{rag_context}",
            }
            static_messages.append(rag_message)
            rag_content = json.dumps([rag_message], sort_keys=True)
            rag_token_count = count_tokens(rag_content, self._encoding)
            _, rag_hash = self._store.lookup(rag_content)

        rag_control = self._update_rag_stability(rag_hash)

        # Phase 4: P1 ΓÇö Count full static prefix tokens with REAL tiktoken
        full_static_content = json.dumps(static_messages, sort_keys=True)
        static_token_count = count_tokens(full_static_content, self._encoding)

        # Phase 5: P5 ΓÇö Full prefix hash for overall cache hit detection
        if rag_control["bypass_active"] and rag_hash is not None:
            is_cached = False
            content_hash = _hash_content(full_static_content)
        else:
            is_cached, content_hash = self._store.lookup(full_static_content)

            if not is_cached:
                self._store.store(full_static_content, static_token_count)

        # Phase 6: Detect cache hits (segmented)
        full_cache_hit = content_hash == self._last_static_hash
        base_cache_hit = base_hash == self._last_base_hash

        self._last_static_hash = content_hash
        self._last_base_hash = base_hash

        # P1: Real token savings tracking
        if full_cache_hit:
            self._store.stats.tokens_saved += static_token_count
        elif base_cache_hit:
            # Partial reuse ΓÇö base prompt was cached even though RAG changed
            self._store.stats.tokens_saved += base_token_count

        # Phase 7: P2 ΓÇö Return CLEAN messages, NO internal metadata injected
        optimized_messages = static_messages + dynamic_messages

        total_token_count = count_tokens(json.dumps(optimized_messages, sort_keys=True), self._encoding)

        result = {
            "messages": optimized_messages,
            "cache_metadata": {
                "static_prefix_hash": content_hash,
                "base_prefix_hash": base_hash,
                "rag_prefix_hash": rag_hash,
                "is_cache_hit": full_cache_hit,
                "is_base_cache_hit": base_cache_hit,
                "cache_eligible": not (rag_control["bypass_active"] and rag_hash is not None),
                "static_messages_count": len(static_messages),
                "dynamic_messages_count": len(dynamic_messages),
                "base_prefix_tokens": base_token_count,
                "rag_prefix_tokens": rag_token_count,
                "static_prefix_tokens": static_token_count,
                "total_tokens": total_token_count,
                "rag_cache_bypass_active": rag_control["bypass_active"],
                "rag_change_streak": rag_control["change_streak"],
                "rag_thrash_threshold": self._rag_thrash_threshold,
                "rag_cache_mode": (
                    "base-only" if rag_control["bypass_active"] and rag_hash is not None else "full-prefix"
                ),
            },
            "stats": self._store.get_stats(),
        }

        # RFC-002 Phase 3: Advisor hints when orchestrator is detected
        orchestrator = get_orchestrator_info()
        if orchestrator.advisor_mode:
            # Compute advisor hints based on token usage patterns
            dynamic_token_count = total_token_count - static_token_count
            dynamic_ratio = round(dynamic_token_count / max(1, total_token_count), 2)

            result["advisor_hints"] = {
                "orchestrator": orchestrator.orchestrator_name,
                "should_trim_now": dynamic_ratio > 0.7,
                "suggested_strategy": ("smart" if dynamic_ratio > 0.7 else "tail"),
                "prefix_stable": full_cache_hit,
                "dynamic_token_ratio": dynamic_ratio,
                "recommendation": (
                    "Static prefix is stable ΓÇö cache savings active."
                    if full_cache_hit
                    else "Static prefix changed ΓÇö cache miss expected this turn."
                ),
            }

        return result

    def get_stats(self) -> dict:
        """Get cache performance statistics."""
        return self._store.get_stats()

    def reset(self) -> None:
        """Reset cache state."""
        self._store.clear()
        self._last_static_hash = None
        self._last_base_hash = None
