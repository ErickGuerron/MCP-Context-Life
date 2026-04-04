from mmcp.cache_manager import CacheLoop
from mmcp.config import get_config


def test_cache_loop_throttles_full_prefix_cache_when_rag_thrash(isolated_data_dir):
    cfg = get_config()
    cfg.cache_rag_thrash_threshold = 2
    cfg.cache_rag_bypass_cooldown = 2

    loop = CacheLoop()
    messages = [
        {"role": "system", "content": "Base instructions"},
        {"role": "user", "content": "Hello"},
    ]

    turn1 = loop.process_messages(messages, rag_context="rag-a")
    turn2 = loop.process_messages(messages, rag_context="rag-b")
    turn3 = loop.process_messages(messages, rag_context="rag-c")

    assert turn1["cache_metadata"]["rag_cache_bypass_active"] is False
    assert turn2["cache_metadata"]["rag_cache_bypass_active"] is False
    assert turn3["cache_metadata"]["rag_cache_bypass_active"] is True
    assert turn3["cache_metadata"]["cache_eligible"] is False
    assert turn3["cache_metadata"]["rag_cache_mode"] == "base-only"
    assert turn3["cache_metadata"]["is_base_cache_hit"] is True

    assert turn3["stats"]["total_lookups"] == turn2["stats"]["total_lookups"] + 2


def test_cache_loop_restores_full_prefix_cache_after_bypass_cooldown(isolated_data_dir):
    cfg = get_config()
    cfg.cache_rag_thrash_threshold = 1
    cfg.cache_rag_bypass_cooldown = 1

    loop = CacheLoop()
    messages = [
        {"role": "system", "content": "Base instructions"},
        {"role": "user", "content": "Hello"},
    ]

    loop.process_messages(messages, rag_context="rag-a")
    bypass_turn = loop.process_messages(messages, rag_context="rag-b")
    recovered_turn = loop.process_messages(messages, rag_context="rag-b")

    assert bypass_turn["cache_metadata"]["rag_cache_bypass_active"] is True
    assert recovered_turn["cache_metadata"]["rag_cache_bypass_active"] is False
    assert recovered_turn["cache_metadata"]["cache_eligible"] is True
    assert recovered_turn["cache_metadata"]["rag_cache_mode"] == "full-prefix"
