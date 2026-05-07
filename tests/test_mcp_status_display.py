"""
Tests for MCP status display (optimization_status enrichment).

Verifies that when advisor_mode is True, the optimization_status field is appended
to tool responses from: optimize_messages, cache_context, intercept_user_request.
"""
import json

import pytest

from mmcp.infrastructure.environment.orchestrator_detector import reset_detection
from mmcp.presentation.mcp.server import (
    cache_context,
    intercept_user_request,
    optimize_messages,
)


# ============================================================
# optimize_messages — optimization_status
# ============================================================


def test_optimize_messages_includes_optimization_status_when_advisor_mode(monkeypatch):
    """RED: optimize_messages should append optimization_status when advisor_mode is True."""
    monkeypatch.setenv("GENTLE_AI_ACTIVE", "1")
    reset_detection()

    messages = json.dumps([
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello! " * 200},
        {"role": "assistant", "content": "How can I help? " * 200},
    ])

    result = json.loads(optimize_messages(messages, max_tokens=500, strategy="smart"))

    assert "optimization_status" in result, (
        "optimization_status must be present when advisor_mode is True"
    )
    status = result["optimization_status"]
    assert "strategy" in status
    assert "original_tokens" in status
    assert "optimized_tokens" in status
    assert "messages_modified" in status
    assert "resulting_prompt" in status
    assert status["strategy"] == "smart"
    assert isinstance(status["original_tokens"], int)
    assert isinstance(status["optimized_tokens"], int)
    assert isinstance(status["messages_modified"], int)
    assert isinstance(status["resulting_prompt"], str)


def test_optimize_messages_no_optimization_status_when_advisor_mode_off(monkeypatch):
    """GREEN: optimize_messages must NOT append optimization_status when advisor_mode is False."""
    monkeypatch.delenv("GENTLE_AI_ACTIVE", raising=False)
    # Also clear any workspace artifact detection
    monkeypatch.setenv("ENGRAM", "")
    monkeypatch.delenv("ENGRAM", raising=False)
    reset_detection()

    # Force advisor_mode off by patching the orchestrator info directly
    from mmcp.infrastructure.environment import orchestrator_detector
    monkeypatch.setattr(orchestrator_detector, "_cached_result", orchestrator_detector.OrchestratorInfo(
        is_detected=False,
        orchestrator_name="none",
        detection_method="none",
        features=[],
        advisor_mode=False,
    ))

    messages = json.dumps([
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello! " * 200},
    ])

    result = json.loads(optimize_messages(messages, max_tokens=500, strategy="smart"))

    assert "optimization_status" not in result, (
        "optimization_status must NOT be present when advisor_mode is False"
    )


def test_optimize_messages_truncated_flag_reflects_resulting_json_size(monkeypatch):
    """
    RED + TRIANGULATE: truncated flag reflects the size of the SERIALIZED
    resulting_messages JSON — not the size of the input.

    When trim reduces a large input, the resulting JSON may be small and
    truncated=False is correct. The flag tells us whether the *result*
    was truncated, not whether the original was large.
    """
    monkeypatch.setenv("GENTLE_AI_ACTIVE", "1")
    reset_detection()

    # Input is large enough that trim MUST cut it down
    messages = json.dumps([
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "x" * 5000},
    ])

    result = json.loads(optimize_messages(messages, max_tokens=500, strategy="smart"))
    status = result["optimization_status"]

    # The serialized JSON of the resulting messages determines truncation
    resulting_json_len = len(json.dumps(result["messages"]))

    assert status["truncated"] == (resulting_json_len > 2048), (
        f"truncated should be {resulting_json_len > 2048} "
        f"(resulting JSON is {resulting_json_len} chars)"
    )
    assert len(status["resulting_prompt"]) <= 2048


def test_optimize_messages_truncated_false_when_short_prompt(monkeypatch):
    """RED: truncated is False when resulting_prompt fits within 2048 chars."""
    monkeypatch.setenv("GENTLE_AI_ACTIVE", "1")
    reset_detection()

    messages = json.dumps([
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hi"},
    ])

    result = json.loads(optimize_messages(messages, max_tokens=500, strategy="smart"))
    status = result["optimization_status"]

    assert status["truncated"] is False, (
        "truncated should be False when resulting_prompt fits within 2048 chars"
    )


def test_optimize_messages_strategy_reflected_in_status(monkeypatch):
    """TRIANGULATE: strategy used must be reflected in optimization_status.strategy."""
    monkeypatch.setenv("GENTLE_AI_ACTIVE", "1")
    reset_detection()

    messages = json.dumps([
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": "answer"},
        {"role": "user", "content": "more"},
    ])

    for strategy in ("tail", "head", "smart"):
        result = json.loads(optimize_messages(messages, max_tokens=200, strategy=strategy))
        assert "optimization_status" in result
        assert result["optimization_status"]["strategy"] == strategy


# ============================================================
# cache_context — optimization_status
# ============================================================


def test_cache_context_includes_optimization_status_when_advisor_mode(monkeypatch):
    """RED: cache_context should append optimization_status when advisor_mode is True."""
    monkeypatch.setenv("GENTLE_AI_ACTIVE", "1")
    reset_detection()

    messages = json.dumps([
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello! " * 200},
        {"role": "assistant", "content": "How can I help? " * 200},
    ])

    result = json.loads(cache_context(messages))

    assert "optimization_status" in result, (
        "optimization_status must be present when advisor_mode is True"
    )
    status = result["optimization_status"]
    assert "strategy" in status
    assert "original_tokens" in status
    assert "optimized_tokens" in status
    assert "messages_modified" in status
    assert "resulting_prompt" in status


def test_cache_context_no_optimization_status_when_advisor_mode_off(monkeypatch):
    """GREEN: cache_context must NOT append optimization_status when advisor_mode is False."""
    monkeypatch.delenv("GENTLE_AI_ACTIVE", raising=False)
    monkeypatch.delenv("ENGRAM", raising=False)
    reset_detection()

    from mmcp.infrastructure.environment import orchestrator_detector
    monkeypatch.setattr(orchestrator_detector, "_cached_result", orchestrator_detector.OrchestratorInfo(
        is_detected=False,
        orchestrator_name="none",
        detection_method="none",
        features=[],
        advisor_mode=False,
    ))

    messages = json.dumps([
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello! " * 200},
    ])

    result = json.loads(cache_context(messages))

    assert "optimization_status" not in result, (
        "optimization_status must NOT be present when advisor_mode is False"
    )


def test_cache_context_truncated_false_when_short(monkeypatch):
    """TRIANGULATE: cache_context truncated is False when prompt fits within 2048."""
    monkeypatch.setenv("GENTLE_AI_ACTIVE", "1")
    reset_detection()

    messages = json.dumps([
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hi"},
    ])

    result = json.loads(cache_context(messages))
    status = result["optimization_status"]

    assert status["truncated"] is False


# ============================================================
# intercept_user_request — ContextPack JSON (D4 design)
# ============================================================


def test_intercept_user_request_returns_context_pack_when_advisor_mode(monkeypatch):
    """intercept_user_request returns legacy contract with D4 sidecar per mcp-status-scoop-upgrade."""
    monkeypatch.setenv("GENTLE_AI_ACTIVE", "1")
    reset_detection()

    request = "Help me optimize my context and trim my message history please"
    result = json.loads(intercept_user_request(request))

    # Legacy contract fields
    assert "intent" in result
    assert "keywords" in result
    assert "advice" in result
    assert "applied_process" in result

    # D4 sidecar
    assert "d4" in result, "D4 output must be under 'd4' key"
    d4 = result["d4"]
    assert "goal" in d4, "ContextPack must have 'goal' field"
    assert "state" in d4, "ContextPack must have 'state' field"
    assert "confidence" in d4, "ContextPack must have 'confidence' field"
    assert "reason" in d4, "ContextPack must have 'reason' field"
    assert "context_budget" in d4, "ContextPack must have 'context_budget' field"
    assert "project_context" in d4, "ContextPack must have 'project_context' field"
    assert "files" in d4, "ContextPack must have 'files' field"
    assert "constraints" in d4, "ContextPack must have 'constraints' field"
    assert "missing_context" in d4, "ContextPack must have 'missing_context' field"
    assert "next_action" in d4, "ContextPack must have 'next_action' field"
    assert d4["state"] in ("LIGHT", "REQUIRED", "CRITICAL")
    assert isinstance(d4["confidence"], float)
    assert isinstance(d4["next_action"], str)


def test_intercept_user_request_context_pack_fields_types(monkeypatch):
    """TRIANGULATE: intercept_user_request D4 sidecar has correct field types."""
    monkeypatch.setenv("GENTLE_AI_ACTIVE", "1")
    reset_detection()

    request = "Hello world this is a test request for context optimization"
    result = json.loads(intercept_user_request(request))

    # D4 sidecar fields
    d4 = result["d4"]
    assert isinstance(d4["goal"], str)
    assert isinstance(d4["state"], str)
    assert isinstance(d4["confidence"], float)
    assert isinstance(d4["reason"], str)
    assert isinstance(d4["context_budget"], str)
    assert isinstance(d4["project_context"], dict)
    assert isinstance(d4["files"], dict)
    assert isinstance(d4["constraints"], list)
    assert isinstance(d4["missing_context"], list)
    assert isinstance(d4["next_action"], str)

    # project_context sub-fields
    pc = d4["project_context"]
    assert "stack" in pc
    assert "architecture" in pc
    assert "testing" in pc
    assert "package_manager" in pc

    # files sub-fields
    files = d4["files"]
    assert "explicit" in files
    assert "inferred" in files
    assert isinstance(files["explicit"], list)
    assert isinstance(files["inferred"], list)


def test_intercept_user_request_no_optimization_status(monkeypatch):
    """intercept_user_request returns legacy contract with D4 sidecar, not optimization_status."""
    monkeypatch.setenv("GENTLE_AI_ACTIVE", "1")
    reset_detection()

    request = "Help me with my code"
    result = json.loads(intercept_user_request(request))

    # No optimization_status at top level
    assert "optimization_status" not in result, (
        "intercept_user_request must return legacy contract with D4 sidecar, not optimization_status"
    )
    # Legacy contract present
    assert "intent" in result
    assert "advice" in result
    # D4 sidecar present
    assert "d4" in result
    assert "state" in result["d4"]


# ============================================================
# Shared helpers — verify optimization_status shape
# ============================================================


@pytest.mark.parametrize("tool_fn,args", [
    (optimize_messages, {"messages": json.dumps([
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello! " * 100},
    ]), "max_tokens": 500, "strategy": "smart"}),
    (cache_context, {"messages": json.dumps([
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello! " * 100},
    ])}),
])
def test_optimization_status_fields_present_and_types_correct(monkeypatch, tool_fn, args):
    """TRIANGULATE: all required fields present with correct types for optimize_messages and cache_context.

    Note: intercept_user_request returns ContextPack JSON per D4 design, not optimization_status.
    """
    monkeypatch.setenv("GENTLE_AI_ACTIVE", "1")
    reset_detection()

    result = json.loads(tool_fn(**args))
    status = result["optimization_status"]

    # Check all required fields exist
    assert "strategy" in status
    assert "original_tokens" in status
    assert "optimized_tokens" in status
    assert "messages_modified" in status
    assert "resulting_prompt" in status
    assert "truncated" in status

    # Check types
    assert isinstance(status["strategy"], str)
    assert isinstance(status["original_tokens"], int)
    assert isinstance(status["optimized_tokens"], int)
    assert isinstance(status["messages_modified"], int)
    assert isinstance(status["resulting_prompt"], str)
    assert isinstance(status["truncated"], bool)

    # Sanity: original >= optimized (tokens should not increase)
    assert status["original_tokens"] >= status["optimized_tokens"]
