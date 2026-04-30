import json

from mmcp.presentation.app_container import AppContainer
from mmcp.presentation.mcp import server
from mmcp.application.features.context.service import ContextService
from mmcp.infrastructure.context.trim_history import TrimResult, trim_messages


class FakeCacheLoop:
    def __init__(self):
        self.calls = []

    def process_messages(self, messages, rag_context=None):
        self.calls.append((messages, rag_context))
        return {
            "messages": messages,
            "cache_metadata": {"rag_context": rag_context, "called": True},
            "stats": {"tokens_saved": 0},
        }


def test_context_service_delegates_cache_context_to_cache_loop():
    cache_loop = FakeCacheLoop()
    service = ContextService(cache_loop=cache_loop)

    payload = service.cache_context([{"role": "user", "content": "hola"}], rag_context="rag")

    assert cache_loop.calls == [([{"role": "user", "content": "hola"}], "rag")]
    assert payload["cache_metadata"]["called"] is True
    assert payload["messages"] == [{"role": "user", "content": "hola"}]


def test_context_service_preserves_trim_contract():
    service = ContextService(cache_loop=FakeCacheLoop())
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]

    result = service.optimize_messages(messages, max_tokens=50, strategy="smart", preserve_recent=2)

    assert isinstance(result, TrimResult)
    assert result.to_dict() == trim_messages(messages, max_tokens=50, strategy="smart", preserve_recent=2).to_dict()


def test_container_reuses_context_service_until_cache_config_changes(isolated_data_dir):
    container = AppContainer()

    first = container.get_context_service()
    second = container.get_context_service()

    assert first is second


def test_container_rebuilds_context_service_when_cache_config_changes(isolated_data_dir):
    from mmcp.infrastructure.environment.config import get_config

    cfg = get_config()
    container = AppContainer()

    first = container.get_context_service()
    cfg.cache_max_entries = 99

    second = container.get_context_service()

    assert first is not second


def test_optimize_messages_tool_routes_through_trim_messages(monkeypatch):
    captured = {}

    def fake_trim_messages(messages, max_tokens, strategy, preserve_recent, encoding):
        captured["args"] = (messages, max_tokens, strategy, preserve_recent, encoding)
        return TrimResult(
            messages=messages,
            original_token_count=10,
            trimmed_token_count=10,
            messages_removed=0,
            strategy_used=strategy,
        )

    monkeypatch.setattr(server, "trim_messages", fake_trim_messages)

    payload = json.loads(
        server.optimize_messages(
            json.dumps([{"role": "user", "content": "hola"}]),
            max_tokens=123,
            strategy="tail",
            preserve_recent=1,
        )
    )

    assert captured["args"][1:] == (123, "tail", 1, "cl100k_base")
    assert payload["diagnostics"]["strategy"] == "tail"


def test_cache_context_tool_routes_through_cache_loop(monkeypatch):
    captured = {}

    class FakeCacheLoop:
        def process_messages(self, messages, rag_context=None):
            captured["args"] = (messages, rag_context)
            return {"messages": messages, "cache_metadata": {"rag_context": rag_context}}

    monkeypatch.setattr(server, "_get_cache_loop", lambda: FakeCacheLoop())

    payload = json.loads(
        server.cache_context(
            json.dumps([{"role": "user", "content": "hola"}]),
            rag_query=None,
            rag_top_k=3,
        )
    )

    assert captured["args"] == ([{"role": "user", "content": "hola"}], None)
    assert payload["cache_metadata"]["rag_context"] is None
