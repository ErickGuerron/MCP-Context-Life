"""
Tests for RFC-002 P3: Orchestrator Detection.

Verifies:
  1. Environment variable detection (GENTLE_AI_ACTIVE, ENGRAM, MCP_ORCHESTRATOR)
  2. Workspace artifact detection (.gemini/, .agent/)
  3. Default behavior when no orchestrator is present
  4. Cache reset works correctly
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from mmcp.infrastructure.environment.orchestrator_detector import (
    OrchestratorInfo,
    _check_env_vars,
    _check_workspace_artifacts,
    detect_orchestrator,
    get_orchestrator_info,
    reset_detection,
)


@pytest.fixture(autouse=True)
def clean_detection():
    """Reset detection cache before and after each test."""
    reset_detection()
    yield
    reset_detection()


class TestEnvVarDetection:
    """Test environment variable detection strategies."""

    def test_gentle_ai_active(self):
        """GENTLE_AI_ACTIVE=1 should detect gentle-ai."""
        with patch.dict(os.environ, {"GENTLE_AI_ACTIVE": "1"}, clear=False):
            result = _check_env_vars()

        assert result is not None
        assert result.is_detected
        assert result.orchestrator_name == "gentle-ai"
        assert result.advisor_mode
        assert "engram" in result.features

    def test_engram_env(self):
        """ENGRAM env var should detect engram orchestrator."""
        with patch.dict(os.environ, {"ENGRAM": "1"}, clear=False):
            result = _check_env_vars()

        assert result is not None
        assert result.is_detected
        assert result.orchestrator_name == "engram"
        assert "persistent_memory" in result.features

    def test_mcp_orchestrator_env(self):
        """MCP_ORCHESTRATOR should detect generic orchestrator."""
        with patch.dict(os.environ, {"MCP_ORCHESTRATOR": "custom-ai"}, clear=False):
            result = _check_env_vars()

        assert result is not None
        assert result.is_detected
        assert result.orchestrator_name == "custom-ai"

    def test_no_env_vars(self):
        """No relevant env vars should return None."""
        # Ensure none of the detection env vars are set
        env_clean = {k: v for k, v in os.environ.items() if k not in ("GENTLE_AI_ACTIVE", "ENGRAM", "MCP_ORCHESTRATOR")}
        with patch.dict(os.environ, env_clean, clear=True):
            result = _check_env_vars()

        assert result is None


class TestWorkspaceDetection:
    """Test workspace artifact detection."""

    def test_gemini_dir_detected(self):
        """Presence of .gemini/ should detect gentle-ai."""
        with tempfile.TemporaryDirectory() as tmp:
            gemini_dir = Path(tmp) / ".gemini"
            gemini_dir.mkdir()

            result = _check_workspace_artifacts(cwd=tmp)

        assert result is not None
        assert result.is_detected
        assert result.orchestrator_name == "gentle-ai"
        assert "workspace:" in result.detection_method

    def test_gemini_with_antigravity(self):
        """Presence of .gemini/antigravity/ should include extra features."""
        with tempfile.TemporaryDirectory() as tmp:
            antigravity_dir = Path(tmp) / ".gemini" / "antigravity"
            antigravity_dir.mkdir(parents=True)

            result = _check_workspace_artifacts(cwd=tmp)

        assert result is not None
        assert "antigravity" in result.features
        assert "skills" in result.features

    def test_agent_dir_detected(self):
        """Presence of .agent/ should detect agent-teams."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".agent").mkdir()
            result = _check_workspace_artifacts(cwd=tmp)

        assert result is not None
        assert result.orchestrator_name == "agent-teams"

    def test_gga_file_detected(self):
        """Presence of .gga should detect the Gentle ecosystem."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".gga").write_text("PROVIDER=gemini")
            result = _check_workspace_artifacts(cwd=tmp)

        assert result is not None
        assert result.orchestrator_name == "gentle-ai"
        assert result.detection_method == "workspace:.gga"

    def test_opencode_atl_dir_detected(self):
        """Presence of .atl/ should detect OpenCode."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".atl").mkdir()
            result = _check_workspace_artifacts(cwd=tmp)

        assert result is not None
        assert result.orchestrator_name == "opencode"
        assert result.detection_method == "workspace:.atl/"
        assert "atl" in result.features

    def test_opencode_home_config_detected_without_explicit_cwd(self):
        """Home .config/opencode/ should be a safe fallback for runtime autodetect."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_home = Path(tmp) / "home"
            fake_workspace = Path(tmp) / "workspace"
            (fake_home / ".config" / "opencode").mkdir(parents=True)
            fake_workspace.mkdir()

            with (
                patch("mmcp.infrastructure.environment.orchestrator_detector.Path.home", return_value=fake_home),
                patch("mmcp.infrastructure.environment.orchestrator_detector.Path.cwd", return_value=fake_workspace),
            ):
                result = _check_workspace_artifacts()

        assert result is not None
        assert result.orchestrator_name == "opencode"
        assert result.detection_method == "home:.config/opencode/"

    def test_no_workspace_artifacts(self):
        """Empty workspace should return None."""
        with tempfile.TemporaryDirectory() as tmp:
            result = _check_workspace_artifacts(cwd=tmp)

        assert result is None


class TestDetectOrchestrator:
    """Test the main detection function."""

    def test_env_takes_priority_over_workspace(self):
        """Env vars should be checked BEFORE workspace artifacts."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".gemini").mkdir()

            with patch.dict(os.environ, {"ENGRAM": "1"}, clear=False):
                result = detect_orchestrator(cwd=tmp)

        # Should detect via env var, not workspace
        assert result.orchestrator_name == "engram"
        assert "env:" in result.detection_method

    def test_no_detection_returns_default(self):
        """No orchestrator should return default OrchestratorInfo."""
        env_clean = {k: v for k, v in os.environ.items() if k not in ("GENTLE_AI_ACTIVE", "ENGRAM", "MCP_ORCHESTRATOR")}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, env_clean, clear=True):
                result = detect_orchestrator(cwd=tmp)

        assert not result.is_detected
        assert result.orchestrator_name == "none"
        assert not result.advisor_mode


class TestCachedDetection:
    """Test the caching behavior of get_orchestrator_info()."""

    def test_cached_result_reused(self):
        """Second call should reuse cached result."""
        env_clean = {k: v for k, v in os.environ.items() if k not in ("GENTLE_AI_ACTIVE", "ENGRAM", "MCP_ORCHESTRATOR")}
        with patch.dict(os.environ, env_clean, clear=True):
            with tempfile.TemporaryDirectory() as tmp:
                result1 = detect_orchestrator(cwd=tmp)
                # Manually set cache
                from mmcp.infrastructure.environment import orchestrator_detector

                orchestrator_detector._cached_result = result1

                result2 = get_orchestrator_info()

        assert result1 is result2

    def test_reset_clears_cache(self):
        """reset_detection() should clear the cache."""
        from mmcp.infrastructure.environment import orchestrator_detector

        orchestrator_detector._cached_result = OrchestratorInfo(is_detected=True, orchestrator_name="test")
        reset_detection()
        assert orchestrator_detector._cached_result is None


class TestOrchestratorInfoSerialization:
    """Test to_dict() serialization."""

    def test_to_dict_structure(self):
        """to_dict() should return all expected fields."""
        info = OrchestratorInfo(
            is_detected=True,
            orchestrator_name="gentle-ai",
            detection_method="env:GENTLE_AI_ACTIVE",
            features=["engram", "sdd"],
            advisor_mode=True,
        )
        d = info.to_dict()

        assert d["is_detected"] is True
        assert d["orchestrator_name"] == "gentle-ai"
        assert d["advisor_mode"] is True
        assert "engram" in d["features"]
