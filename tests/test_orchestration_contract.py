import json

from mmcp.infrastructure.environment.orchestrator_detector import reset_detection
from mmcp.presentation.mcp.server import get_orchestration_advice, orchestration_resource


def test_orchestration_resource_exposes_contract(monkeypatch):
    monkeypatch.setenv("GENTLE_AI_ACTIVE", "1")
    reset_detection()

    payload = json.loads(orchestration_resource())

    assert payload["detected_orchestrator"]["orchestrator_name"] == "gentle-ai"
    assert payload["integration_level"] == "heuristic-advisor"
    assert payload["capabilities"]["orchestration_advice"] == "get_orchestration_advice"
    assert "optimize_messages" in payload["recommended_flow"]


def test_orchestration_advice_recommends_trim(monkeypatch):
    monkeypatch.setenv("GENTLE_AI_ACTIVE", "1")
    reset_detection()

    messages = json.dumps(
        [
            {"role": "system", "content": "policy " * 200},
            {"role": "user", "content": "question " * 400},
        ]
    )

    payload = json.loads(get_orchestration_advice(messages, max_tokens=500))

    assert payload["orchestrator"]["orchestrator_name"] == "gentle-ai"
    assert payload["advice"]["recommended_next_tool"] == "optimize_messages"
    assert payload["advice"]["should_trim_now"] is True
    assert payload["advice"]["urgency"] in ("high", "medium")


def test_orchestration_advice_recommends_cache_when_healthy(monkeypatch):
    monkeypatch.setenv("GENTLE_AI_ACTIVE", "1")
    reset_detection()

    messages = json.dumps(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hola"},
        ]
    )

    payload = json.loads(get_orchestration_advice(messages, max_tokens=2000))

    assert payload["advice"]["recommended_next_tool"] == "cache_context"
    assert payload["advice"]["should_trim_now"] is False
    assert isinstance(payload["advice"]["estimated_savings_tokens"], int)
