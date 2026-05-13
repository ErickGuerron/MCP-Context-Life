"""
Sleep Context Tool - Context-Life (CL)

RFC-002 P5: Persist session learnings at task end.
Called by LLM at task end (solo-agent) or by orchestrator (multi-agent).

NOTE: This module defines the function but does NOT register as an MCP tool.
Registration happens in server.py via mcp.add_tool().
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from mmcp.domain.session_state import PhaseGuardError, SessionState, SessionStateMachine
from mmcp.infrastructure.session_id_resolver import resolve as resolve_session_id

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


def sleep_context() -> str:
    """
    Persist current session learnings to server.
    Called by LLM at task end (solo-agent) or by orchestrator (multi-agent).

    Returns: {"status": "persisted", "session_id": str}
    """
    # Bypass if DISABLE_AUTOINVOKE=1
    if os.environ.get("DISABLE_AUTOINVOKE") == "1":
        return json.dumps({
            "status": "bypassed",
            "reason": "DISABLE_AUTOINVOKE=1",
            "session_id": None
        })

    # Derive session ID server-side
    session_id = resolve_session_id()

    if session_id is None:
        return json.dumps({
            "status": "no_session",
            "session_id": None
        })

    # Handle state machine transitions
    sm = _get_state_machine()
    try:
        current = sm.get_current_state()
        if current in (SessionState.WAKING, SessionState.ACTIVE):
            sm.transition(SessionState.SLEEPING)
        sm.transition(SessionState.IDLE)
    except PhaseGuardError:
        # Reset on invalid transition
        sm._current_state = SessionState.IDLE

    # Persist to filesystem
    config_dir = Path.home() / ".config" / "context-life" / "sessions"
    config_dir.mkdir(parents=True, exist_ok=True)

    session_file = config_dir / session_id[:16] / "state.json"  # Use first 16 chars of session_id as folder name
    session_file.parent.mkdir(parents=True, exist_ok=True)

    state_data = {
        "session_id": session_id,
        "state": sm.get_current_state().value,
        "persisted": True
    }

    session_file.write_text(json.dumps(state_data, indent=2), encoding="utf-8")

    return json.dumps({
        "status": "persisted",
        "session_id": session_id,
        "state": sm.get_current_state().value,
        "path": str(session_file)
    })