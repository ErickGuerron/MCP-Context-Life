from mmcp.infrastructure.context.trim_history import count_messages_tokens, trim_messages


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


def test_trim_smart_uses_explicit_system_budget_fallback():
    messages = [
        {"role": "system", "content": "policy " * 400},
        {"role": "developer", "content": "constraints " * 300},
        {"role": "user", "content": "hola"},
    ]

    result = trim_messages(messages, max_tokens=40, strategy="smart", preserve_recent=1)
    payload = result.to_dict()

    assert result.trimmed_token_count <= 40
    assert payload["diagnostics"]["system_budget_fallback"] is True
    assert payload["diagnostics"]["system_budget_fallback_mode"] in ("minimal_anchor", "empty_output")

    if result.messages:
        assert result.messages == [
            {"role": "system", "content": "[CL Trim Fallback] Increase max_tokens."}
        ] or result.messages[0]["content"].startswith("[CL Trim Fallback]")
        assert "policy" not in result.messages[0]["content"].lower()
