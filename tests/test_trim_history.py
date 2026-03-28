import json

import pytest

from mmcp.trim_history import trim_messages, count_messages_tokens
from mmcp.token_counter import count_tokens

def test_trim_smart_protects_anchors():
    """
    Test that the smart trim strategy preserves exact system messages 
    and handles overflow gracefully without dropping them.
    """
    messages = [
        {"role": "system", "content": "You are a very long system prompt... " * 50},
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "How can I help?"},
        {"role": "user", "content": "Please explain Python... " * 10},
    ]
    
    # Trim to 200 tokens using smart strategy
    result = trim_messages(messages, max_tokens=200, strategy="smart", preserve_recent=2)
    trimmed = result.messages
    
    # The system message MUST be retained. If it exceeds 200 tokens alone,
    # the fallback (System Digest) must kick in.
    roles = [m["role"] for m in trimmed]
    
    # Asserting that a system message always remains at index 0.
    assert roles[0] == "system", "First message must be system anchor"
    
    # Budget check
    trimmed_tokens = count_messages_tokens(trimmed)
    assert trimmed_tokens <= 200, f"Token budget exceeded: {trimmed_tokens} > 200"
