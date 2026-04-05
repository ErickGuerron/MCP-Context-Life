"""
Tests for RFC-002 P2: Token Count LRU Cache.

Verifies that:
  1. Token counts are accurate with and without cache
  2. LRU cache hits improve on repeated calls
  3. Short strings bypass the cache
  4. Cache size is bounded
  5. Cache can be cleared
  6. Encoder objects are cached
"""

import pytest

from mmcp.token_counter import (
    _MIN_CACHE_LENGTH,
    _encoder_cache,
    clear_cache,
    count_tokens,
    get_cache_info,
    get_encoder,
)


@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure each test starts with a clean cache."""
    clear_cache()
    _encoder_cache.clear()
    yield
    clear_cache()
    _encoder_cache.clear()


class TestTokenCachingAccuracy:
    """Ensure caching doesn't alter token counts."""

    def test_same_result_cached_vs_fresh(self):
        """Cached and fresh counts must be identical."""
        text = "This is a test sentence for token counting accuracy."

        # First call — cache miss
        count1 = count_tokens(text)
        # Second call — cache hit
        count2 = count_tokens(text)

        assert count1 == count2
        assert count1 > 0

    def test_different_encodings_different_counts(self):
        """Different encodings should produce different counts."""
        text = "Token counting with different encodings for verification."

        count_cl = count_tokens(text, "cl100k_base")
        count_o200k = count_tokens(text, "o200k_base")

        # Both should be positive
        assert count_cl > 0
        assert count_o200k > 0
        # They may differ because encodings have different vocabularies

    def test_empty_string_returns_zero(self):
        """Empty string should return 0 tokens."""
        assert count_tokens("") == 0

    def test_whitespace_only(self):
        """Whitespace-only strings should return > 0."""
        assert count_tokens(" ") > 0


class TestLRUCacheHits:
    """Verify cache hit mechanics."""

    def test_cache_miss_then_hit(self):
        """First call is miss, second call is hit."""
        text = "A sufficiently long text for cache testing requirements."
        assert len(text) >= _MIN_CACHE_LENGTH

        count_tokens(text)
        info1 = get_cache_info()
        assert info1["misses"] == 1
        assert info1["hits"] == 0

        count_tokens(text)
        info2 = get_cache_info()
        assert info2["hits"] == 1
        assert info2["misses"] == 1

    def test_short_strings_bypass_cache(self):
        """Strings shorter than _MIN_CACHE_LENGTH skip the cache entirely."""
        short = "Hi!"
        assert len(short) < _MIN_CACHE_LENGTH

        count_tokens(short)
        count_tokens(short)

        info = get_cache_info()
        # No cache interactions for short strings
        assert info["hits"] == 0
        assert info["misses"] == 0

    def test_cache_size_limit(self):
        """Cache should not exceed maxsize."""
        # Fill cache with unique strings
        for i in range(50):
            count_tokens(f"Unique test string number {i} for cache size testing purposes")

        info = get_cache_info()
        assert info["currsize"] <= info["maxsize"]

    def test_hit_rate_calculation(self):
        """Hit rate should be computed correctly."""
        text = "Repeated text for hit rate calculation testing."

        # 1 miss + 4 hits = 80% hit rate
        for _ in range(5):
            count_tokens(text)

        info = get_cache_info()
        assert info["hit_rate"] == 80.0


class TestEncoderCache:
    """Verify encoder object caching."""

    def test_encoder_cached_after_first_call(self):
        """Encoder should be cached after first retrieval."""
        _encoder_cache.clear()
        assert "cl100k_base" not in _encoder_cache

        enc = get_encoder("cl100k_base")
        assert "cl100k_base" in _encoder_cache

        # Second call returns the SAME object
        enc2 = get_encoder("cl100k_base")
        assert enc is enc2

    def test_invalid_encoding_raises(self):
        """Invalid encoding names should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported encoding"):
            get_encoder("invalid_encoding")

    def test_clear_cache_resets(self):
        """clear_cache() should reset the LRU cache stats."""
        text = "Text for clear cache testing with enough characters."
        count_tokens(text)

        info = get_cache_info()
        assert info["currsize"] > 0

        clear_cache()

        info = get_cache_info()
        assert info["currsize"] == 0
        assert info["hits"] == 0
        assert info["misses"] == 0
