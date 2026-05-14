"""Domain models for Context-Life."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UsageEvent:
    """Normalized usage telemetry event."""

    session_id: str
    event_type: str = "standard"
    accounting_mode: str = "captured"
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    uncached_input_tokens: int = 0
    effective_saved_tokens: int = 0
    host_name: str = "unknown"
    agent_name: str = "unknown"
    provider_name: str = "unknown"
    model_name: str = "unknown"
    tool_name: str = "unknown"
    latency_ms: float = 0.0
    timestamp: float = 0.0
