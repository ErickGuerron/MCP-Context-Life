"""
Telemetry Service Module ΓÇö Context-Life (CL)

Implements SOLID & DDD principles to decouple the MCP server's core logic
from the specific telemetry infrastructure (SessionStore/SQLite).

This module provides:
1. TelemetryService: A domain service acting as a port to persistence.
2. @track_telemetry: An AOP (Aspect-Oriented) decorator that silently
   intercepts MCP tool calls, extracts metrics, and fires telemetry events.
"""

from __future__ import annotations

import json
import os
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from mmcp.infrastructure.environment.config import get_config
from mmcp.infrastructure.environment.orchestrator_detector import get_orchestrator_info
from mmcp.infrastructure.persistence.session_store import SessionStore, UsageEvent

_telemetry_store: SessionStore | None = None
_telemetry_store_db_path: Path | None = None


def _get_telemetry_store() -> SessionStore:
    """Resolve the telemetry store lazily so config overrides hit the active DB."""
    global _telemetry_store, _telemetry_store_db_path

    current_db_path = Path(get_config().resolve_cache_db_path())
    if _telemetry_store is None or _telemetry_store_db_path != current_db_path:
        _telemetry_store = SessionStore(current_db_path)
        _telemetry_store_db_path = current_db_path
    return _telemetry_store


class TelemetryService:
    """
    Domain Service enforcing Dependency Inversion Principle (DIP).
    Isolates the rest of the application from the SQLite persistence logic.
    """

    @staticmethod
    def log_usage(event: UsageEvent) -> None:
        """
        Record a telemetry event into the underlying persistence store.
        If we eventually move from SQLite to a remote API, this is the
        only point of change.
        """
        try:
            _get_telemetry_store().record_usage(event)
        except Exception as e:
            # Telemetry is non-critical path; failing to log shouldn't crash the server
            import logging

            logging.error(f"Failed to record telemetry: {e}")


def _coerce_int(value: Any, default: int = 0) -> int:
    """Best-effort integer coercion for telemetry payloads."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_model_name(model_name: str | None) -> str:
    """Normalize telemetry model names from env hints."""
    value = (model_name or "").strip()
    return value or "unknown"


def _infer_provider_from_model(model_name: str) -> str:
    """Infer provider from a normalized model name."""
    lowered = model_name.lower()
    if lowered == "unknown":
        return "unknown"

    provider_prefixes = (
        ("openai/", "openai"),
        ("anthropic/", "anthropic"),
        ("google/", "google"),
        ("gemini/", "google"),
        ("openrouter/", "openrouter"),
        ("opencode/", "opencode"),
        ("gentle/", "gentle-ai"),
        ("gentle-ai/", "gentle-ai"),
    )
    for prefix, provider in provider_prefixes:
        if lowered.startswith(prefix):
            return provider

    if lowered.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    if lowered.startswith(("claude-", "claude")):
        return "anthropic"
    if lowered.startswith(("gemini-", "models/gemini")):
        return "google"

    return "unknown"


def _detect_model_context(orchestrator_name: str) -> tuple[str, str]:
    """Detect provider/model from inherited host environment variables."""
    explicit_model_hints = (
        ("OPENCODE_MODEL", "opencode"),
        ("GENTLE_MODEL", "gentle-ai"),
        ("GENTLE_AI_MODEL", "gentle-ai"),
        ("OPENAI_MODEL", "openai"),
        ("ANTHROPIC_MODEL", "anthropic"),
        ("GEMINI_MODEL", "google"),
        ("GOOGLE_MODEL", "google"),
        ("OPENROUTER_MODEL", "openrouter"),
        ("MCP_MODEL", None),
        ("LLM_MODEL", None),
        ("MODEL", None),
    )
    for env_var, preferred_provider in explicit_model_hints:
        value = _normalize_model_name(os.environ.get(env_var))
        if value != "unknown":
            provider = preferred_provider or _infer_provider_from_model(value)
            if provider == "unknown" and orchestrator_name in {"opencode", "gentle-ai"}:
                provider = orchestrator_name
            return provider, value

    provider_env_fallbacks = (
        ("OPENAI_API_KEY", "openai"),
        ("ANTHROPIC_API_KEY", "anthropic"),
        ("GEMINI_API_KEY", "google"),
        ("GOOGLE_API_KEY", "google"),
    )
    for env_var, provider in provider_env_fallbacks:
        if os.environ.get(env_var):
            return provider, f"{provider}/unknown"

    if orchestrator_name == "opencode":
        return "opencode", "opencode/unknown"
    if orchestrator_name == "gentle-ai":
        return "gentle-ai", "gentle-ai/unknown"

    return "unknown", "unknown"


def _extract_usage_metrics(payload: Any) -> dict[str, int]:
    """Extract per-call usage metrics from tool JSON payloads."""
    usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "effective_saved_tokens": 0,
        "cached_input_tokens": 0,
        "uncached_input_tokens": 0,
    }

    if not isinstance(payload, dict):
        return usage

    def _lookup(*path: str) -> Any:
        current: Any = payload
        for segment in path:
            if not isinstance(current, dict):
                return None
            current = current.get(segment)
        return current

    def _first_int(*paths: tuple[str, ...], default: int = 0) -> int:
        for path in paths:
            value = _lookup(*path)
            if value is not None:
                return _coerce_int(value, default)
        return default

    if "token_count" in payload:
        usage["input_tokens"] = _coerce_int(payload.get("token_count"))
        usage["uncached_input_tokens"] = usage["input_tokens"]
        return usage

    top_level_or_nested_total = _first_int(
        ("total_tokens",),
        ("metrics", "total_tokens"),
        ("health", "metrics", "total_tokens"),
    )
    if top_level_or_nested_total:
        usage["input_tokens"] = top_level_or_nested_total
        usage["uncached_input_tokens"] = usage["input_tokens"]

    diagnostics = _lookup("diagnostics")
    if isinstance(diagnostics, dict):
        usage["input_tokens"] = _coerce_int(diagnostics.get("original_tokens"), usage["input_tokens"])
        usage["output_tokens"] = _coerce_int(diagnostics.get("trimmed_tokens"), usage["output_tokens"])
        usage["effective_saved_tokens"] = _coerce_int(diagnostics.get("tokens_saved"))
        usage["uncached_input_tokens"] = usage["input_tokens"]
        return usage

    cache_metadata = _lookup("cache_metadata")
    if isinstance(cache_metadata, dict):
        total_tokens = _coerce_int(cache_metadata.get("total_tokens"))
        static_prefix_tokens = _coerce_int(cache_metadata.get("static_prefix_tokens"))
        base_prefix_tokens = _coerce_int(cache_metadata.get("base_prefix_tokens"))
        usage["input_tokens"] = total_tokens
        usage["output_tokens"] = total_tokens

        if cache_metadata.get("is_cache_hit"):
            usage["cached_input_tokens"] = static_prefix_tokens
        elif cache_metadata.get("is_base_cache_hit"):
            usage["cached_input_tokens"] = base_prefix_tokens

        usage["effective_saved_tokens"] = usage["cached_input_tokens"]
        usage["uncached_input_tokens"] = max(0, total_tokens - usage["cached_input_tokens"])
        return usage

    nested_health_total = _first_int(("metrics", "total_tokens"), ("health", "metrics", "total_tokens"))
    if nested_health_total:
        usage["input_tokens"] = nested_health_total
        usage["uncached_input_tokens"] = nested_health_total

    return usage


def track_telemetry(tool_name: str) -> Callable:
    """
    Decorator implementing an AOP (Aspect-Oriented Programming) wrapper.
    Ensures that core LLM optimization tools don't violate the Single
    Responsibility Principle (SRP) by knowing about analytics mechanisms.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 1. Start timer
            start_time = time.perf_counter()

            # 2. Execute original domain logic
            result = func(*args, **kwargs)

            # 3. Stop timer
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            # 4. Extract telemetry payload (async/non-blocking ideally, but safe to inline)
            try:
                _process_telemetry_event(tool_name, latency_ms, args, kwargs, result)
            except Exception as e:
                import logging

                logging.warning(f"Telemetry extraction failed for {tool_name}: {e}")

            return result

        return wrapper

    return decorator


def _process_telemetry_event(tool_name: str, latency_ms: float, args: tuple, kwargs: dict, result: Any) -> None:
    """
    Internal helper to construct the UsageEvent by inspecting
    input parameters and the JSON output of the tools.
    """
    # Grab orchestrator metadata (who is calling us?)
    orchestrator = get_orchestrator_info()
    host_name = "context-life-server"
    agent_name = "UnknownAgent"

    # Use orchestrator detection to identify the calling agent
    if orchestrator.is_detected:
        agent_name = orchestrator.orchestrator_name

    provider_name, model_name = _detect_model_context(agent_name)
    payload = result
    try:
        if isinstance(result, str):
            payload = json.loads(result)
    except Exception:
        pass

    usage_metrics = _extract_usage_metrics(payload)

    event = UsageEvent(
        session_id=str(int(time.time())),  # Session proxy
        input_tokens=max(0, usage_metrics["input_tokens"]),
        output_tokens=max(0, usage_metrics["output_tokens"]),
        cached_input_tokens=max(0, usage_metrics["cached_input_tokens"]),
        uncached_input_tokens=max(0, usage_metrics["uncached_input_tokens"]),
        effective_saved_tokens=max(0, usage_metrics["effective_saved_tokens"]),
        host_name=host_name,
        agent_name=agent_name,
        provider_name=provider_name,
        model_name=model_name,
        tool_name=tool_name,
        latency_ms=round(latency_ms, 2),
        timestamp=time.time(),
    )

    # 5. Delegate to domain service
    TelemetryService.log_usage(event)
