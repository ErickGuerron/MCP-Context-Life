from mmcp.infrastructure.persistence.cache_manager import CacheStore


class FakePrefixCacheStore:
    def __init__(self):
        self.lookup_calls = []
        self.record_hit_calls = []
        self.store_calls = []
        self.evict_calls = []
        self.clear_calls = 0
        self.lookup_result = None

    def lookup_prefix(self, content_hash: str):
        self.lookup_calls.append(content_hash)
        return self.lookup_result

    def record_prefix_hit(self, content_hash: str) -> None:
        self.record_hit_calls.append(content_hash)

    def store_prefix(self, content_hash: str, token_count: int) -> None:
        self.store_calls.append((content_hash, token_count))

    def evict_old_prefixes(self, max_entries: int) -> None:
        self.evict_calls.append(max_entries)

    def clear(self) -> None:
        self.clear_calls += 1


def test_cache_store_uses_injected_session_store_for_lookup_hit():
    session_store = FakePrefixCacheStore()
    session_store.lookup_result = (42, 3)
    store = CacheStore(max_entries=10, session_store=session_store)

    is_cached, content_hash = store.lookup('[{"role": "system", "content": "Base"}]')

    assert is_cached is True
    assert len(content_hash) == 16
    assert session_store.lookup_calls == [content_hash]
    assert session_store.record_hit_calls == [content_hash]
    assert store.get_token_count(content_hash) == 42


def test_cache_store_uses_injected_session_store_for_store_and_eviction():
    session_store = FakePrefixCacheStore()
    store = CacheStore(max_entries=5, session_store=session_store)

    content_hash = store.store('[{"role": "system", "content": "Base"}]', 42)

    assert len(content_hash) == 16
    assert session_store.store_calls == [(content_hash, 42)]
    assert session_store.evict_calls == [5]
