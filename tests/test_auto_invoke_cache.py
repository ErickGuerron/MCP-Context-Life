"""
Tests for AutoInvokeCache: TTL cache with SHA-256 key derivation.
"""

import threading
import time

from mmcp.orchestration.auto_invoke_cache import AutoInvokeCache


class TestAutoInvokeCacheKeyDerivation:
    """Test SHA-256 key derivation from operation signature."""

    def test_identical_requests_produce_same_key(self):
        """Identical (host, agent, provider, model, operation, args) produce same SHA-256 key."""
        cache = AutoInvokeCache()

        key1 = cache._derive_key(
            host="localhost",
            agent="test-agent",
            provider="openai",
            model="gpt-4",
            operation="chat",
            args={"prompt": "hello", "max_tokens": 100},
        )
        key2 = cache._derive_key(
            host="localhost",
            agent="test-agent",
            provider="openai",
            model="gpt-4",
            operation="chat",
            args={"prompt": "hello", "max_tokens": 100},
        )

        assert key1 == key2
        assert len(key1) == 64  # SHA-256 hex length

    def test_different_args_produce_different_key(self):
        """Different args produce different SHA-256 hashes."""
        cache = AutoInvokeCache()

        key1 = cache._derive_key(
            host="localhost",
            agent="test-agent",
            provider="openai",
            model="gpt-4",
            operation="chat",
            args={"prompt": "hello"},
        )
        key2 = cache._derive_key(
            host="localhost",
            agent="test-agent",
            provider="openai",
            model="gpt-4",
            operation="chat",
            args={"prompt": "world"},
        )

        assert key1 != key2

    def test_different_operation_produce_different_key(self):
        """Different operation name produces different key."""
        cache = AutoInvokeCache()

        key1 = cache._derive_key(
            host="localhost",
            agent="test-agent",
            provider="openai",
            model="gpt-4",
            operation="chat",
            args={"prompt": "hello"},
        )
        key2 = cache._derive_key(
            host="localhost",
            agent="test-agent",
            provider="openai",
            model="gpt-4",
            operation="complete",
            args={"prompt": "hello"},
        )

        assert key1 != key2


class TestAutoInvokeCacheTTL:
    """Test TTL expiration behavior."""

    def test_cache_hit_returns_stored_result(self):
        """Cache hit returns stored result without re-execution."""
        cache = AutoInvokeCache(ttl_seconds=60)
        key = cache._derive_key(
            host="localhost",
            agent="test-agent",
            provider="openai",
            model="gpt-4",
            operation="chat",
            args={"prompt": "hello"},
        )

        stored_result = {"content": "cached response"}
        cache.set(key, stored_result)

        result = cache.get(key)
        assert result == stored_result

    def test_cache_miss_returns_none(self):
        """Cache miss returns None when entry absent."""
        cache = AutoInvokeCache(ttl_seconds=60)
        key = cache._derive_key(
            host="localhost",
            agent="test-agent",
            provider="openai",
            model="gpt-4",
            operation="chat",
            args={"prompt": "hello"},
        )

        result = cache.get(key)
        assert result is None

    def test_ttl_expiration_forces_re_execution(self):
        """Expired TTL causes cache miss."""
        cache = AutoInvokeCache(ttl_seconds=1)  # 1 second TTL
        key = cache._derive_key(
            host="localhost",
            agent="test-agent",
            provider="openai",
            model="gpt-4",
            operation="chat",
            args={"prompt": "hello"},
        )

        cache.set(key, {"content": "original"})
        time.sleep(1.1)

        result = cache.get(key)
        assert result is None

    def test_ttl_not_expired_returns_cached(self):
        """Within TTL window, cached result is returned."""
        cache = AutoInvokeCache(ttl_seconds=10)
        key = cache._derive_key(
            host="localhost",
            agent="test-agent",
            provider="openai",
            model="gpt-4",
            operation="chat",
            args={"prompt": "hello"},
        )

        cache.set(key, {"content": "original"})
        time.sleep(0.1)

        result = cache.get(key)
        assert result == {"content": "original"}


class TestAutoInvokeCacheDeduplication:
    """Test concurrent request deduplication."""

    def test_concurrent_deduplication_only_one_execution(self):
        """Only one execution occurs for concurrent identical keys; others wait for result."""
        cache = AutoInvokeCache(ttl_seconds=60)
        key = cache._derive_key(
            host="localhost",
            agent="test-agent",
            provider="openai",
            model="gpt-4",
            operation="chat",
            args={"prompt": "hello"},
        )

        execution_count = 0
        results_received = []

        def slow_execute():
            nonlocal execution_count
            execution_count += 1
            time.sleep(0.5)  # Simulate slow execution
            return {"content": "result"}

        threads = []
        for _ in range(3):
            t = threading.Thread(
                target=lambda: results_received.append(cache.get_or_execute(key, slow_execute))
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only one actual execution occurred
        assert execution_count == 1
        # All threads received the same result
        assert all(r == {"content": "result"} for r in results_received)


class TestAutoInvokeCacheManagement:
    """Test cache invalidation, clear, and stats."""

    def test_invalidate_removes_entry(self):
        """cache.invalidate(key) removes the entry."""
        cache = AutoInvokeCache(ttl_seconds=60)
        key = cache._derive_key(
            host="localhost",
            agent="test-agent",
            provider="openai",
            model="gpt-4",
            operation="chat",
            args={"prompt": "hello"},
        )

        cache.set(key, {"content": "original"})
        cache.invalidate(key)

        result = cache.get(key)
        assert result is None

    def test_clear_removes_all_entries(self):
        """cache.clear() removes all entries."""
        cache = AutoInvokeCache(ttl_seconds=60)

        cache.set(
            cache._derive_key(
                host="localhost", agent="a", provider="openai", model="gpt-4", operation="c", args={}
            ),
            {"content": "a"},
        )
        cache.set(
            cache._derive_key(
                host="localhost", agent="b", provider="openai", model="gpt-4", operation="c", args={}
            ),
            {"content": "b"},
        )

        cache.clear()

        stats = cache.get_stats()
        assert stats["entries"] == 0

    def test_get_stats_returns_dict(self):
        """get_stats() returns a dict with entries, hits, misses."""
        cache = AutoInvokeCache(ttl_seconds=60)

        stats = cache.get_stats()
        assert "entries" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert isinstance(stats["entries"], int)


class TestAutoInvokeCacheOversizedResult:
    """Test max entry size guard."""

    def test_oversized_result_not_cached(self):
        """Results exceeding max_entry_size_bytes are not cached."""
        cache = AutoInvokeCache(ttl_seconds=60, max_entry_size_bytes=100)
        key = cache._derive_key(
            host="localhost",
            agent="test-agent",
            provider="openai",
            model="gpt-4",
            operation="chat",
            args={"prompt": "hello"},
        )

        oversized_result = {"content": "x" * 200}  # > 100 bytes

        cache.set(key, oversized_result)

        # Entry should NOT be stored
        result = cache.get(key)
        assert result is None

        stats = cache.get_stats()
        assert stats["skipped_too_large"] == 1


class TestAutoInvokeCacheBypass:
    """Test cache bypass when disabled."""

    def test_bypass_when_disabled(self):
        """When auto_invoke_cache.enabled is False, cache is not consulted."""
        cache = AutoInvokeCache(enabled=False, ttl_seconds=60)
        key = cache._derive_key(
            host="localhost",
            agent="test-agent",
            provider="openai",
            model="gpt-4",
            operation="chat",
            args={"prompt": "hello"},
        )

        # Store a value
        cache.set(key, {"content": "stored"})

        # get() should return None (bypass)
        result = cache.get(key)
        assert result is None

        # get_or_execute() should execute without storing
        execution_called = []

        def execute():
            execution_called.append(True)
            return {"content": "executed"}

        result = cache.get_or_execute(key, execute)
        assert result == {"content": "executed"}
        assert len(execution_called) == 1

        # The result should NOT have been cached
        stats = cache.get_stats()
        assert stats["entries"] == 0
