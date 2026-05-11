"""
Tests for RFC-002 P5: Stack Detection (solo-agent vs orchestrator).

Detection logic (priority order):
1. DISABLE_AUTOINVOKE=1 → SOLO_AGENT (bypass)
2. ENGRAM_ACTIVE=1 or ENGRAM_SESSION_ID set → ORCHESTRATOR
3. GENTLE_AI_ACTIVE=1 → ORCHESTRATOR (custom orchestrator override)
4. Otherwise → SOLO_AGENT
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from mmcp.orchestration.stack_detector import StackType, detect


class TestDetectStackType:
    """Test stack type detection."""

    def test_golden_path_orchestrator(self):
        """GENTLE_AI_ACTIVE=1 → ORCHESTRATOR (no .gga required)."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"GENTLE_AI_ACTIVE": "1"}, clear=False):
                result = detect(cwd=tmp)

        assert result == StackType.ORCHESTRATOR

    def test_golden_path_solo_agent(self):
        """No signals → SOLO_AGENT."""
        with tempfile.TemporaryDirectory() as tmp:
            env_clean = {k: v for k, v in os.environ.items() if k not in ("ENGRAM_ACTIVE", "ENGRAM_SESSION_ID", "GENTLE_AI_ACTIVE", "DISABLE_AUTOINVOKE")}
            with patch.dict(os.environ, env_clean, clear=True):
                result = detect(cwd=tmp)

        assert result == StackType.SOLO_AGENT

    def test_gga_only_no_env_signal(self):
        """.gga exists but no GENTLE_AI_ACTIVE → SOLO_AGENT."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".gga").touch()
            env_clean = {k: v for k, v in os.environ.items() if k not in ("GENTLE_AI_ACTIVE", "DISABLE_AUTOINVOKE")}
            with patch.dict(os.environ, env_clean, clear=True):
                result = detect(cwd=tmp)

        assert result == StackType.SOLO_AGENT

    def test_engram_active_signal(self):
        """ENGRAM_ACTIVE=1 → ORCHESTRATOR."""
        with tempfile.TemporaryDirectory() as tmp:
            env_clean = {k: v for k, v in os.environ.items() if k not in ("ENGRAM_ACTIVE", "ENGRAM_SESSION_ID", "GENTLE_AI_ACTIVE", "DISABLE_AUTOINVOKE")}
            with patch.dict(os.environ, env_clean, clear=True):
                with patch.dict(os.environ, {"ENGRAM_ACTIVE": "1"}, clear=False):
                    result = detect(cwd=tmp)

        assert result == StackType.ORCHESTRATOR

    def test_engram_session_id_signal(self):
        """ENGRAM_SESSION_ID set → ORCHESTRATOR."""
        with tempfile.TemporaryDirectory() as tmp:
            env_clean = {k: v for k, v in os.environ.items() if k not in ("ENGRAM_ACTIVE", "ENGRAM_SESSION_ID", "GENTLE_AI_ACTIVE", "DISABLE_AUTOINVOKE")}
            with patch.dict(os.environ, env_clean, clear=True):
                with patch.dict(os.environ, {"ENGRAM_SESSION_ID": "test-session-123"}, clear=False):
                    result = detect(cwd=tmp)

        assert result == StackType.ORCHESTRATOR

    def test_gentle_ai_active_alone_triggers_orchestrator(self):
        """GENTLE_AI_ACTIVE=1 alone (no .gga needed) → ORCHESTRATOR."""
        with tempfile.TemporaryDirectory() as tmp:
            # No .gga file, just the env var
            env_clean = {k: v for k, v in os.environ.items() if k not in ("GENTLE_AI_ACTIVE", "ENGRAM_ACTIVE", "ENGRAM_SESSION_ID", "DISABLE_AUTOINVOKE")}
            with patch.dict(os.environ, env_clean, clear=True):
                with patch.dict(os.environ, {"GENTLE_AI_ACTIVE": "1"}, clear=False):
                    result = detect(cwd=tmp)

        assert result == StackType.ORCHESTRATOR

    def test_disable_autoinvoke_bypasses(self):
        """DISABLE_AUTOINVOKE=1 → always SOLO_AGENT regardless of signals."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".gga").touch()
            with patch.dict(os.environ, {"GENTLE_AI_ACTIVE": "1", "DISABLE_AUTOINVOKE": "1"}, clear=False):
                result = detect(cwd=tmp)

        assert result == StackType.SOLO_AGENT

    def test_disable_autoinvoke_no_signals(self):
        """DISABLE_AUTOINVOKE=1 with no other signals → SOLO_AGENT."""
        with tempfile.TemporaryDirectory() as tmp:
            env_clean = {k: v for k, v in os.environ.items() if k not in ("GENTLE_AI_ACTIVE", "DISABLE_AUTOINVOKE")}
            with patch.dict(os.environ, env_clean, clear=True):
                with patch.dict(os.environ, {"DISABLE_AUTOINVOKE": "1"}, clear=False):
                    result = detect(cwd=tmp)

        assert result == StackType.SOLO_AGENT