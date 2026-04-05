import json
import sqlite3

from mmcp.config import get_config
from mmcp.orchestrator_detector import OrchestratorInfo
from mmcp.server import count_messages_tokens_tool
from mmcp.session_store import SessionStore
from mmcp.telemetry_service import _detect_model_context, _process_telemetry_event


def test_detect_model_context_prefers_explicit_openai_env(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.4")

    provider, model = _detect_model_context("gentle-ai")

    assert provider == "openai"
    assert model == "gpt-5.4"


def test_detect_model_context_falls_back_to_opencode_hint(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    provider, model = _detect_model_context("opencode")

    assert provider == "opencode"
    assert model == "opencode/unknown"


def test_process_telemetry_event_uses_trim_diagnostics(monkeypatch):
    captured = {}

    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.4")
    monkeypatch.setattr(
        "mmcp.telemetry_service.get_orchestrator_info",
        lambda: OrchestratorInfo(is_detected=True, orchestrator_name="gentle-ai"),
    )
    monkeypatch.setattr(
        "mmcp.telemetry_service.TelemetryService.log_usage",
        lambda event: captured.setdefault("event", event),
    )

    result = json.dumps(
        {
            "messages": [{"role": "user", "content": "hola"}],
            "diagnostics": {
                "original_tokens": 1200,
                "trimmed_tokens": 700,
                "tokens_saved": 500,
            },
        }
    )

    _process_telemetry_event("optimize_messages", 12.5, (), {}, result)

    event = captured["event"]
    assert event.agent_name == "gentle-ai"
    assert event.provider_name == "openai"
    assert event.model_name == "gpt-5.4"
    assert event.input_tokens == 1200
    assert event.output_tokens == 700
    assert event.effective_saved_tokens == 500
    assert event.uncached_input_tokens == 1200


def test_process_telemetry_event_uses_cache_metadata_for_saved_tokens(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "mmcp.telemetry_service.get_orchestrator_info",
        lambda: OrchestratorInfo(is_detected=True, orchestrator_name="opencode"),
    )
    monkeypatch.setattr(
        "mmcp.telemetry_service.TelemetryService.log_usage",
        lambda event: captured.setdefault("event", event),
    )

    result = json.dumps(
        {
            "messages": [{"role": "user", "content": "hola"}],
            "cache_metadata": {
                "total_tokens": 900,
                "static_prefix_tokens": 320,
                "base_prefix_tokens": 180,
                "is_cache_hit": False,
                "is_base_cache_hit": True,
            },
            "stats": {"tokens_saved": 99999},
        }
    )

    _process_telemetry_event("cache_context", 8.0, (), {}, result)

    event = captured["event"]
    assert event.provider_name == "opencode"
    assert event.model_name == "opencode/unknown"
    assert event.input_tokens == 900
    assert event.output_tokens == 900
    assert event.cached_input_tokens == 180
    assert event.uncached_input_tokens == 720
    assert event.effective_saved_tokens == 180


def test_process_telemetry_event_uses_nested_health_metrics(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "mmcp.telemetry_service.get_orchestrator_info",
        lambda: OrchestratorInfo(is_detected=True, orchestrator_name="opencode"),
    )
    monkeypatch.setattr(
        "mmcp.telemetry_service.TelemetryService.log_usage",
        lambda event: captured.setdefault("event", event),
    )

    result = json.dumps(
        {
            "orchestrator": {"orchestrator_name": "opencode"},
            "health": {
                "health_score": 82,
                "metrics": {
                    "total_tokens": 4321,
                    "max_tokens": 8000,
                },
            },
            "advice": {"recommended_next_tool": "cache_context"},
        }
    )

    _process_telemetry_event("get_orchestration_advice", 4.2, (), {}, result)

    event = captured["event"]
    assert event.input_tokens == 4321
    assert event.output_tokens == 0
    assert event.uncached_input_tokens == 4321


def test_count_messages_tokens_persists_usage_to_active_sqlite_db(isolated_data_dir, monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.4")
    monkeypatch.setattr(
        "mmcp.telemetry_service.get_orchestrator_info",
        lambda: OrchestratorInfo(is_detected=True, orchestrator_name="gentle-ai"),
    )

    payload = json.dumps(
        [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Contame cuántos tokens gasto."},
        ]
    )

    result = json.loads(count_messages_tokens_tool(payload))
    db_path = get_config().resolve_cache_db_path()
    store = SessionStore(db_path)
    weekly = store.get_weekly_usage()

    assert "gpt-5.4" in weekly
    assert weekly["gpt-5.4"]["accounted_input_tokens"] == result["total_tokens"]
    assert weekly["gpt-5.4"]["activity_tokens"] == result["total_tokens"]

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT provider_name, model_name, tool_name, input_tokens, output_tokens FROM usage_events"
        ).fetchone()

    assert row == ("openai", "gpt-5.4", "count_messages_tokens", result["total_tokens"], 0)
