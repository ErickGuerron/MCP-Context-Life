import json

from mmcp.infrastructure.environment.orchestrator_detector import OrchestratorInfo


class FakeTelemetryStore:
    def __init__(self):
        self.calls = []

    def record_usage(self, event):
        self.calls.append(event)


def test_build_usage_event_uses_trim_diagnostics(monkeypatch):
    from mmcp.application.features.telemetry.service import build_usage_event

    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.4")
    payload = json.dumps(
        {
            "diagnostics": {
                "original_tokens": 1200,
                "trimmed_tokens": 700,
                "tokens_saved": 500,
            }
        }
    )

    event = build_usage_event(
        "optimize_messages",
        12.5,
        payload,
        OrchestratorInfo(is_detected=True, orchestrator_name="gentle-ai"),
    )

    assert event.agent_name == "gentle-ai"
    assert event.provider_name == "openai"
    assert event.model_name == "gpt-5.4"
    assert event.input_tokens == 1200
    assert event.output_tokens == 700
    assert event.effective_saved_tokens == 500
    assert event.uncached_input_tokens == 1200


def test_build_usage_event_uses_cache_metadata_when_present(monkeypatch):
    from mmcp.application.features.telemetry.service import build_usage_event

    payload = json.dumps(
        {
            "cache_metadata": {
                "total_tokens": 900,
                "static_prefix_tokens": 320,
                "base_prefix_tokens": 180,
                "is_cache_hit": False,
                "is_base_cache_hit": True,
            },
            "health": {"metrics": {"total_tokens": 4321}},
        }
    )

    event = build_usage_event(
        "cache_context",
        8.0,
        payload,
        OrchestratorInfo(is_detected=True, orchestrator_name="opencode"),
    )

    assert event.provider_name == "opencode"
    assert event.model_name == "opencode/unknown"
    assert event.input_tokens == 900
    assert event.output_tokens == 900
    assert event.cached_input_tokens == 180
    assert event.uncached_input_tokens == 720
    assert event.effective_saved_tokens == 180


def test_telemetry_service_persists_usage_through_injected_store():
    from mmcp.application.features.telemetry.service import TelemetryService

    store = FakeTelemetryStore()
    service = TelemetryService(store)

    service.record_tool_call(
        "get_orchestration_advice",
        4.2,
        json.dumps(
            {
                "health": {"metrics": {"total_tokens": 4321}},
                "advice": {"recommended_next_tool": "cache_context"},
            }
        ),
        OrchestratorInfo(is_detected=True, orchestrator_name="opencode"),
    )

    assert len(store.calls) == 1
    event = store.calls[0]
    assert event.tool_name == "get_orchestration_advice"
    assert event.input_tokens == 4321
    assert event.output_tokens == 0
    assert event.uncached_input_tokens == 4321
