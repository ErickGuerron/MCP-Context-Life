"""
AutoInvokeCache: TTL cache with SHA-256 key derivation and concurrent deduplication.

This module provides a thread-safe, TTL-based cache for auto-invoke results with:
- SHA-256 key derivation from (host, agent, provider, model, operation, args_json)
- Automatic TTL expiration
- Concurrent request deduplication (only one execution for identical concurrent keys)
- Manual invalidation and clear operations
- Max entry size guard to prevent memory exhaustion
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class CacheEntry:
    """A single cache entry with TTL and metadata."""

    value: Any
    created_at: float
    expires_at: float
    entry_id: str  # unique ID to handle hash collisions


@dataclass
class CacheStats:
    """Cache statistics counters."""

    hits: int = 0
    misses: int = 0
    skipped_too_large: int = 0
    entries: int = 0


class AutoInvokeCache:
    """
    Thread-safe TTL cache with SHA-256 key derivation and concurrent deduplication.

    Key derivation uses SHA-256 over canonical JSON of:
    (host, agent, provider, model, operation_name, normalized_args_json)
    """

    def __init__(
        self,
        enabled: bool = True,
        ttl_seconds: int = 60,
        max_entry_size_bytes: int = 1048576,
    ):
        """
        Initialize AutoInvokeCache.

        Args:
            enabled: If False, all cache operations are no-ops (bypass mode)
            ttl_seconds: Time-to-live for cache entries
            max_entry_size_bytes: Maximum size for cached results; larger results are skipped
        """
        self._enabled = enabled
        self._ttl_seconds = ttl_seconds
        self._max_entry_size_bytes = max_entry_size_bytes
        self._store: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._waiting: Dict[str, List[threading.Event]] = {}
        self._stats = CacheStats()

    def _derive_key(
        self,
        host: str,
        agent: str,
        provider: str,
        model: str,
        operation: str,
        args: Dict[str, Any],
    ) -> str:
        """Derive SHA-256 key from operation signature."""
        canonical = json.dumps(
            (host, agent, provider, model, operation, args),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if a cache entry has expired."""
        return time.monotonic() >= entry.expires_at

    def _entry_size_bytes(self, value: Any) -> int:
        """Estimate size of a value in bytes."""
        try:
            return len(json.dumps(value).encode("utf-8"))
        except Exception:
            return 0

    def get(self, key: str) -> Optional[Any]:
        """Get cached value for key, or None if not found/expired."""
        if not self._enabled:
            return None

        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._stats.misses += 1
                return None

            if self._is_expired(entry):
                del self._store[key]
                self._stats.entries = len(self._store)
                self._stats.misses += 1
                return None

            self._stats.hits += 1
            return entry.value

    def set(self, key: str, value: Any) -> None:
        """Store value in cache with TTL."""
        if not self._enabled:
            return

        size = self._entry_size_bytes(value)
        if size > self._max_entry_size_bytes:
            self._stats.skipped_too_large += 1
            return

        with self._lock:
            now = time.monotonic()
            entry = CacheEntry(
                value=value,
                created_at=now,
                expires_at=now + self._ttl_seconds,
                entry_id=uuid.uuid4().hex,
            )
            self._store[key] = entry
            self._stats.entries = len(self._store)

    def invalidate(self, key: str) -> None:
        """Remove a specific entry from the cache."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                self._stats.entries = len(self._store)

    def clear(self) -> None:
        """Remove all entries from the cache."""
        with self._lock:
            self._store.clear()
            self._stats.entries = 0

    def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        with self._lock:
            return {
                "entries": len(self._store),
                "hits": self._stats.hits,
                "misses": self._stats.misses,
                "skipped_too_large": self._stats.skipped_too_large,
            }

    def get_or_execute(
        self, key: str, execute_fn: Callable[[], Any]
    ) -> Any:
        """
        Get cached result or execute if not cached.

        For concurrent identical keys, only one execution occurs while others wait.
        """
        if not self._enabled:
            return execute_fn()

        # Fast path: check cache without lock
        with self._lock:
            entry = self._store.get(key)
            if entry is not None and not self._is_expired(entry):
                self._stats.hits += 1
                return entry.value

            # Check if another thread is already executing this key
            if key in self._waiting:
                # Wait for the other thread to complete
                event = threading.Event()
                self._waiting[key].append(event)
                lock_released = True
            else:
                # We'll execute; mark that we're working on this key
                self._waiting[key] = []
                lock_released = False

        if lock_released:
            # Wait for the executing thread
            event.wait()
            with self._lock:
                self._stats.hits += 1
                entry = self._store.get(key)
                return entry.value if entry else None

        # Execute the function
        try:
            result = execute_fn()
            self.set(key, result)
            return result
        finally:
            # Signal all waiting threads and clear
            with self._lock:
                events = self._waiting.pop(key, [])
            for event in events:
                event.set()
