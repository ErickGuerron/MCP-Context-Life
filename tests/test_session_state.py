"""
Tests for RFC-002 P5: Session State Machine.

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

import pytest

from mmcp.domain.session_state import PhaseGuardError, SessionState, SessionStateMachine


class TestSessionStateEnum:
    """Test SessionState enum values."""

    def test_session_state_values(self):
        """SessionState should have all expected values."""
        assert SessionState.IDLE.value == "idle"
        assert SessionState.WAKING.value == "waking"
        assert SessionState.ACTIVE.value == "active"
        assert SessionState.SLEEPING.value == "sleeping"
        assert SessionState.HANDS_OFF.value == "hands_off"


class TestSessionStateMachine:
    """Test SessionStateMachine transitions."""

    def test_initial_state_is_idle(self):
        """New machine should start in IDLE state."""
        machine = SessionStateMachine()
        assert machine.get_current_state() == SessionState.IDLE

    def test_valid_transition_idle_to_waking(self):
        """IDLE → WAKING is valid."""
        machine = SessionStateMachine()
        result = machine.transition(SessionState.WAKING)
        assert result == SessionState.WAKING
        assert machine.get_current_state() == SessionState.WAKING

    def test_valid_transition_waking_to_active(self):
        """WAKING → ACTIVE is valid."""
        machine = SessionStateMachine()
        machine.transition(SessionState.WAKING)
        result = machine.transition(SessionState.ACTIVE)
        assert result == SessionState.ACTIVE
        assert machine.get_current_state() == SessionState.ACTIVE

    def test_valid_transition_active_to_sleeping(self):
        """ACTIVE → SLEEPING is valid."""
        machine = SessionStateMachine()
        machine.transition(SessionState.WAKING)
        machine.transition(SessionState.ACTIVE)
        result = machine.transition(SessionState.SLEEPING)
        assert result == SessionState.SLEEPING
        assert machine.get_current_state() == SessionState.SLEEPING

    def test_valid_transition_sleeping_to_idle(self):
        """SLEEPING → IDLE is valid."""
        machine = SessionStateMachine()
        machine.transition(SessionState.WAKING)
        machine.transition(SessionState.ACTIVE)
        machine.transition(SessionState.SLEEPING)
        result = machine.transition(SessionState.IDLE)
        assert result == SessionState.IDLE
        assert machine.get_current_state() == SessionState.IDLE

    def test_valid_transition_idle_to_hands_off(self):
        """IDLE → HANDS_OFF is valid."""
        machine = SessionStateMachine()
        result = machine.transition(SessionState.HANDS_OFF)
        assert result == SessionState.HANDS_OFF
        assert machine.get_current_state() == SessionState.HANDS_OFF

    def test_valid_transition_hands_off_to_idle(self):
        """HANDS_OFF → IDLE is valid."""
        machine = SessionStateMachine()
        machine.transition(SessionState.HANDS_OFF)
        result = machine.transition(SessionState.IDLE)
        assert result == SessionState.IDLE
        assert machine.get_current_state() == SessionState.IDLE

    def test_invalid_transition_idle_to_active_raises(self):
        """IDLE → ACTIVE is invalid and raises PhaseGuardError."""
        machine = SessionStateMachine()
        with pytest.raises(PhaseGuardError):
            machine.transition(SessionState.ACTIVE)

    def test_invalid_transition_waking_to_sleeping_raises(self):
        """WAKING → SLEEPING is invalid and raises PhaseGuardError."""
        machine = SessionStateMachine()
        machine.transition(SessionState.WAKING)
        with pytest.raises(PhaseGuardError):
            machine.transition(SessionState.SLEEPING)

    def test_invalid_transition_active_to_idle_raises(self):
        """ACTIVE → IDLE is invalid and raises PhaseGuardError."""
        machine = SessionStateMachine()
        machine.transition(SessionState.WAKING)
        machine.transition(SessionState.ACTIVE)
        with pytest.raises(PhaseGuardError):
            machine.transition(SessionState.IDLE)

    def test_invalid_transition_sleeping_to_active_raises(self):
        """SLEEPING → ACTIVE is invalid and raises PhaseGuardError."""
        machine = SessionStateMachine()
        machine.transition(SessionState.WAKING)
        machine.transition(SessionState.ACTIVE)
        machine.transition(SessionState.SLEEPING)
        with pytest.raises(PhaseGuardError):
            machine.transition(SessionState.ACTIVE)

    def test_invalid_transition_hands_off_to_waking_raises(self):
        """HANDS_OFF → WAKING is invalid and raises PhaseGuardError."""
        machine = SessionStateMachine()
        machine.transition(SessionState.HANDS_OFF)
        with pytest.raises(PhaseGuardError):
            machine.transition(SessionState.WAKING)

    def test_error_message_contains_from_and_to_states(self):
        """PhaseGuardError message should mention source and target states."""
        machine = SessionStateMachine()
        try:
            machine.transition(SessionState.ACTIVE)
            pytest.fail("Expected PhaseGuardError")
        except PhaseGuardError as e:
            assert "idle" in str(e).lower()
            assert "active" in str(e).lower()
