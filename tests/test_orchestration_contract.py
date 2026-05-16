import json

from mmcp.infrastructure.environment.orchestrator_detector import reset_detection
from mmcp.presentation.mcp.server import (
    get_orchestration_advice,
    intercept_user_request,
    orchestration_resource,
    preflight_request,
)


def test_orchestration_resource_exposes_contract(monkeypatch):
    monkeypatch.setenv("GENTLE_AI_ACTIVE", "1")
    reset_detection()

    payload = json.loads(orchestration_resource())

    assert payload["detected_orchestrator"]["orchestrator_name"] == "gentle-ai"
    assert payload["integration_level"] == "heuristic-advisor"
    assert payload["capabilities"]["orchestration_advice"] == "get_orchestration_advice"
    assert payload["capabilities"]["preflight_prompt"] == "preflight_request"
    assert payload["capabilities"]["intercept"] == "intercept_user_request"
    assert payload["recommended_flow"][0] == "preflight_request"
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


def test_intercept_user_request_routes_feature_request(monkeypatch):
    monkeypatch.setenv("GENTLE_AI_ACTIVE", "1")
    reset_detection()

    request = (
        "Quiero que me crees un dashboard interactivo para la empresa mi negocio en el cual se meustre "
        "las ganancias del mes y la deuda generada el anterior año"
    )

    payload = json.loads(intercept_user_request(request))

    assert payload["intent"] == "feature_request"
    assert payload["advice"]["recommended_next_tool"] == "search_context"
    assert payload["applied_process"][0] == "normalize_request"
    assert any(keyword in payload["keywords"] for keyword in ("dashboard", "ganancias", "deuda"))


def test_preflight_request_prompt_primes_router():
    messages = preflight_request("Quiero un dashboard para ventas y deuda")

    assert messages[0]["role"] == "system"
    assert "intercept_user_request" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "dashboard" in messages[1]["content"].lower()
