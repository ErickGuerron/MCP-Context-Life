"""
Tests to ensure the CacheStore logic successfully saves to and restores from
the SQLite SessionStore.
"""

from mmcp.cache_manager import CacheStore

def test_cache_persistence(isolated_data_dir):
    """
    Simulates sending a RAG static prefix payload, turning off the server,
    turning it back on (new CacheStore instance), and verifying the SQLite
    persistence correctly reconstructs the hit.
    """
    
    # 1. Start Server A
    store_A = CacheStore(max_entries=10)
    content = '[{"role": "system", "content": "You are a helpful coding assistant"}]'
    token_count = 100
    
    # First lookup should be a miss
    is_cached_A, hash_A = store_A.lookup(content)
    assert not is_cached_A
    assert store_A.stats.cache_misses == 1
    
    # Store it
    store_A.store(content, token_count)
    
    # Second lookup inside the same server should be a hit (L1 Cache)
    is_cached_A_2, _ = store_A.lookup(content)
    assert is_cached_A_2
    assert store_A.stats.cache_hits == 1
    
    # Turn Server A off (store_A is destroyed in memory)
    del store_A
    
    # 2. Start Server B (Simulating a console restart)
    store_B = CacheStore(max_entries=10)
    
    # The L1 memory dictionary `_entries` is empty, but `lookup` should
    # query the L2 SQLite SessionStore and recover the payload hash!
    is_cached_B, hash_B = store_B.lookup(content)
    
    assert is_cached_B, "The cache should have survived across process restarts via SQLite!"
    assert hash_A == hash_B
    assert store_B.stats.cache_hits == 1
    assert store_B.stats.cache_misses == 0
    
    # Token count should have been recovered
    recovered_tokens = store_B.get_token_count(hash_B)
    assert recovered_tokens == token_count
