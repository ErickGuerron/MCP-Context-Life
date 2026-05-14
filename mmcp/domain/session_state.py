"""
Session State Machine - Context-Life (CL)

RFC-002 P5: Manages session lifecycle states.

SessionState enum: IDLE, WAKING, ACTIVE, SLEEPING, HANDS_OFF

Valid transitions:
- IDLE → WAKING
- WAKING → ACTIVE
- ACTIVE → SLEEPING
- SLEEPING → IDLE
- IDLE → HANDS_OFF
- HANDS_OFF → IDLE

Invalid transitions raise PhaseGuardError.
"""

from __future__ import annotations

from enum import Enum


class SessionState(Enum):
    IDLE = "idle"
    WAKING = "waking"
    ACTIVE = "active"
    SLEEPING = "sleeping"
    HANDS_OFF = "hands_off"


class PhaseGuardError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, from_state: SessionState, to_state: SessionState):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid transition from {from_state.value} to {to_state.value}")


# Valid transitions map: from_state -> set of allowed to_states
_VALID_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.IDLE: {SessionState.WAKING, SessionState.HANDS_OFF},
    SessionState.WAKING: {SessionState.ACTIVE},
    SessionState.ACTIVE: {SessionState.SLEEPING},
    SessionState.SLEEPING: {SessionState.IDLE},
    SessionState.HANDS_OFF: {SessionState.IDLE},
}


class SessionStateMachine:
    """State machine for session lifecycle management."""

    def __init__(self) -> None:
        self._current_state: SessionState = SessionState.IDLE

    def transition(self, to: SessionState) -> SessionState:
        """
        Attempt to transition to a new state.

        Args:
            to: The target state to transition to.

        Returns:
            The new state after transition.

        Raises:
            PhaseGuardError: If the transition is not valid.
        """
        allowed = _VALID_TRANSITIONS.get(self._current_state, set())
        if to not in allowed:
            raise PhaseGuardError(self._current_state, to)

        self._current_state = to
        return self._current_state

    def get_current_state(self) -> SessionState:
        """Get the current state."""
        return self._current_state
