"""
Tests for auto_invoke and sleep_context tools.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from mmcp.domain.session_state import SessionState
from mmcp.presentation.mcp.tools.auto_invoke import (
    _reset_state_machine,
    autoinvoke_context,
)
from mmcp.presentation.mcp.tools.sleep_context import (
    _reset_state_machine as reset_sleep_state_machine,
    sleep_context,
)


class TestAutoinvokeContext:
    """Tests for autoinvoke_context tool."""

    def setup_method(self):
        """Reset state machine before each test."""
        _reset_state_machine()

    def test_invalid_stack_type_returns_error(self):
        """autoinvoke_context returns error for invalid stack_type."""
        result = json.loads(autoinvoke_context("invalid-type"))
        assert "error" in result
        assert "Invalid stack_type" in result["error"]

    def test_valid_solo_agent_returns_awakened(self):
        """autoinvoke_context with solo-agent returns awakened status."""
        result = json.loads(autoinvoke_context("solo-agent"))
        assert result["status"] == "awakened"
        assert result["stack_type_detected"] == "solo-agent"
        assert result["active_session_id"] is not None
        assert result["level"] in ("REQUIRED", "LIGHT", "CRITICAL")

    def test_valid_orchestrator_returns_delegated(self):
        """autoinvoke_context with orchestrator returns delegated status."""
        # Mock detection as ORCHESTRATOR
        with patch("mmcp.presentation.mcp.tools.auto_invoke.detect_stack") as mock_detect:
            from mmcp.orchestration.stack_detector import StackType
            mock_detect.return_value = StackType.ORCHESTRATOR

            result = json.loads(autoinvoke_context("orchestrator"))
            assert result["status"] == "delegated"
            assert result["stack_type_detected"] == "orchestrator"

    @patch.dict(os.environ, {"DISABLE_AUTOINVOKE": "1"})
    def test_disable_autoinvoke_bypasses(self):
        """DISABLE_AUTOINVOKE=1 returns bypassed status."""
        _reset_state_machine()
        result = json.loads(autoinvoke_context("solo-agent"))
        assert result["status"] == "bypassed"
        assert result["reason"] == "DISABLE_AUTOINVOKE=1"
        assert result["active_session_id"] is None

    def test_session_id_is_server_computed(self):
        """autoinvoke_context does not accept session_id as parameter."""
        result = json.loads(autoinvoke_context("solo-agent"))
        # session_id should be derived server-side, not passed in
        assert result["active_session_id"] is not None
        # Verify it's a SHA256 hash (64 chars)
        assert len(result["active_session_id"]) == 64

    def test_state_machine_transitions_to_active(self):
        """autoinvoke_context transitions state machine to ACTIVE for solo-agent."""
        _reset_state_machine()
        result = json.loads(autoinvoke_context("solo-agent"))
        assert result["session_state"]["current"] == "active"


class TestSleepContext:
    """Tests for sleep_context tool."""

    def setup_method(self):
        """Reset state machine before each test."""
        reset_sleep_state_machine()

    def test_sleep_returns_persisted_status(self):
        """sleep_context returns persisted status with session_id."""
        result = json.loads(sleep_context())
        assert result["status"] == "persisted"
        assert result["session_id"] is not None
        assert result["state"] == "idle"

    def test_sleep_persists_to_filesystem(self):
        """sleep_context persists state to filesystem."""
        result = json.loads(sleep_context())
        assert result["status"] == "persisted"
        assert "path" in result
        path = Path(result["path"])
        assert path.exists()
        # Verify content
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["session_id"] == result["session_id"]
        assert data["persisted"] is True

    @patch.dict(os.environ, {"DISABLE_AUTOINVOKE": "1"})
    def test_disable_autoinvoke_bypasses_sleep(self):
        """DISABLE_AUTOINVOKE=1 makes sleep_context return bypassed."""
        reset_sleep_state_machine()
        result = json.loads(sleep_context())
        assert result["status"] == "bypassed"
        assert result["reason"] == "DISABLE_AUTOINVOKE=1"

    def test_sleep_without_prior_autoinvoke_still_works(self):
        """sleep_context works even without prior autoinvoke (new session)."""
        result = json.loads(sleep_context())
        assert result["status"] == "persisted"
        assert result["session_id"] is not None

    def test_state_transitions_to_idle_after_sleep(self):
        """sleep_context transitions state machine to IDLE."""
        # First invoke
        autoinvoke_context("solo-agent")
        # Then sleep
        result = json.loads(sleep_context())
        assert result["state"] == "idle"


class TestIntegration:
    """Integration tests for auto-invoke flow."""

    def setup_method(self):
        """Reset state machines before each test."""
        _reset_state_machine()
        reset_sleep_state_machine()

    def test_full_cycle_wake_to_sleep(self):
        """Full solo-agent cycle: wake → sleep."""
        # Wake
        wake_result = json.loads(autoinvoke_context("solo-agent"))
        assert wake_result["status"] == "awakened"
        session_id = wake_result["active_session_id"]

        # Sleep
        sleep_result = json.loads(sleep_context())
        assert sleep_result["status"] == "persisted"
        assert sleep_result["session_id"] == session_id

    def test_state_file_created_at_expected_path(self):
        """State file is created at ~/.config/context-life/sessions/{id}/state.json."""
        result = json.loads(sleep_context())
        path = Path(result["path"])
        # Should be in ~/.config/context-life/sessions/
        assert ".config" in str(path)
        assert "context-life" in str(path)
        assert "sessions" in str(path)
        assert path.name == "state.json"