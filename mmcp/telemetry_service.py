"""
Telemetry Service Module — Context-Life (CL)

Implements SOLID & DDD principles to decouple the MCP server's core logic
from the specific telemetry infrastructure (SessionStore/SQLite).

This module provides:
1. TelemetryService: A domain service acting as a port to persistence.
2. @track_telemetry: An AOP (Aspect-Oriented) decorator that silently
   intercepts MCP tool calls, extracts metrics, and fires telemetry events.
"""

from __future__ import annotations

import json
import time
from functools import wraps
from typing import Any, Callable

from mmcp.orchestrator_detector import get_orchestrator_info
from mmcp.session_store import SessionStore, UsageEvent

# Global singleton repository
_telemetry_store = SessionStore()


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
            _telemetry_store.record_usage(event)
        except Exception as e:
            # Telemetry is non-critical path; failing to log shouldn't crash the server
            import logging
            logging.error(f"Failed to record telemetry: {e}")


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


def _process_telemetry_event(
    tool_name: str,
    latency_ms: float,
    args: tuple,
    kwargs: dict,
    result: Any
) -> None:
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

    # Default baseline stats
    input_tokens = 0
    output_tokens = 0
    effective_saved = 0
    model_name = "local" # We default to local if unspecified, MCP tools generally don't know the remote model
    
    # Try to parse the result if it's JSON (most of our tools return JSON strings)
    try:
        if isinstance(result, str):
            parsed = json.loads(result)
            
            # Tools like `count_messages_tokens_tool` or `count_tokens_tool`
            if "token_count" in parsed:
                input_tokens = parsed["token_count"]
            elif "total_tokens" in parsed:
                input_tokens = parsed["total_tokens"]
                
            # Tools like `optimize_messages` or `cache_context`
            if "metrics" in parsed:
                metrics = parsed["metrics"]
                input_tokens = metrics.get("total_tokens", 0)
                output_tokens = metrics.get("reduced_tokens", 0)
                if "cache_savings" in metrics:
                    effective_saved = metrics["cache_savings"]
                else:
                    # Generic trimming savings
                    effective_saved = input_tokens - output_tokens
                    
            # Identify model if they pass it inside the message context? 
            # For now, MCP servers don't naturally see 'model_name'.
            # We map context budget actions as specific to standard budget operations.
            model_name = "context-life-mcp" 
    except Exception:
        pass

    event = UsageEvent(
        session_id=str(int(time.time())),  # Session proxy
        input_tokens=input_tokens,
        output_tokens=abs(output_tokens),
        effective_saved_tokens=max(0, effective_saved),
        host_name=host_name,
        agent_name=agent_name,
        provider_name="local",
        model_name=model_name,
        tool_name=tool_name,
        latency_ms=round(latency_ms, 2),
        timestamp=time.time()
    )

    # 5. Delegate to domain service
    TelemetryService.log_usage(event)
