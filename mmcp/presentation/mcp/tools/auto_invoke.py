"""
Auto-Invoke Context Tool - Context-Life (CL)

RFC-002 P5: Auto-invoke context-life at prompt boundaries using MCP tool.
Stack type (solo-agent vs orchestrator) is detected via StackDetector.
Session ID is derived server-side via SessionIdResolver.

NOTE: This module defines the function but does NOT register as an MCP tool.
Registration happens in server.py via mcp.add_tool().
"""

from __future__ import annotations

import json
import os
from typing import Optional

from mmcp.domain.session_state import PhaseGuardError, SessionState, SessionStateMachine
from mmcp.infrastructure.session_id_resolver import resolve as resolve_session_id
from mmcp.orchestration.stack_detector import StackType, detect as detect_stack

# Module-level state machine for session tracking
_state_machine: Optional[SessionStateMachine] = None


def _get_state_machine() -> SessionStateMachine:
    global _state_machine
    if _state_machine is None:
        _state_machine = SessionStateMachine()
    return _state_machine


def _reset_state_machine() -> None:
    global _state_machine
    _state_machine = None


def autoinvoke_context(stack_type: str) -> str:
    """
    Auto-invoke context-life at prompt boundaries.

    Session ID is derived server-side (not a parameter).

    Args:
        stack_type: Either "solo-agent" or "orchestrator" (delegated to advisor).

    Returns JSON: {
        "context_items": [...],
        "session_state": {...},
        "recommendations": [...],
        "active_session_id": str,  # server-computed
        "level": "REQUIRED" | "LIGHT" | "CRITICAL"
    }

    Raises:
        ValueError: If stack_type is not valid.
    """
    # Validate stack_type
    valid_types = {"solo-agent", "orchestrator"}
    if stack_type not in valid_types:
        return json.dumps({
            "error": f"Invalid stack_type '{stack_type}'. Must be one of: {valid_types}",
            "stack_type_received": stack_type
        })

    # Bypass if DISABLE_AUTOINVOKE=1
    if os.environ.get("DISABLE_AUTOINVOKE") == "1":
        return json.dumps({
            "status": "bypassed",
            "reason": "DISABLE_AUTOINVOKE=1",
            "stack_type": stack_type,
            "active_session_id": None,
            "context_items": [],
            "session_state": {"current": "idle"},
            "recommendations": ["Proceed with normal agent workflow"],
            "level": "LIGHT"
        })

    # Detect actual stack type
    detected_stack = detect_stack()

    # Override stack_type validation based on detection
    # If detected_stack is ORCHESTRATOR but stack_type is "solo-agent",
    # we still proceed with detected stack type
    actual_stack = detected_stack

    # Derive session ID server-side
    session_id = resolve_session_id()

    # Handle state machine transitions
    sm = _get_state_machine()
    try:
        if actual_stack == StackType.SOLO_AGENT:
            sm.transition(SessionState.WAKING)
            sm.transition(SessionState.ACTIVE)
        else:
            # Orchestrator: HANDS_OFF mode
            sm.transition(SessionState.HANDS_OFF)
    except PhaseGuardError:
        # If transition fails, reset to IDLE
        sm._current_state = SessionState.IDLE
        if actual_stack == StackType.SOLO_AGENT:
            sm.transition(SessionState.WAKING)
            sm.transition(SessionState.ACTIVE)
        else:
            sm.transition(SessionState.HANDS_OFF)

    # Build response based on stack type
    if actual_stack == StackType.SOLO_AGENT:
        # Solo-agent: load from intercept_user_request and local state
        response = {
            "status": "awakened",
            "stack_type_detected": "solo-agent",
            "active_session_id": session_id,
            "context_items": [],
            "session_state": {
                "current": sm.get_current_state().value,
                "mode": "solo-agent"
            },
            "recommendations": [
                "Call intercept_user_request for context extraction",
                "Proceed with task execution"
            ],
            "level": "REQUIRED"
        }
    else:
        # Orchestrator: delegate to context-life-advisor
        response = {
            "status": "delegated",
            "stack_type_detected": "orchestrator",
            "active_session_id": session_id,
            "context_items": [],
            "session_state": {
                "current": sm.get_current_state().value,
                "mode": "orchestrator"
            },
            "recommendations": [
                "Delegate to context-life-advisor sub-agent",
                "Await ContextPack from advisor"
            ],
            "level": "REQUIRED"
        }

    return json.dumps(response)