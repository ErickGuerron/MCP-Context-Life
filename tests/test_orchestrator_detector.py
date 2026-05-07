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
    OrchestratorFeatures,
    OrchestratorInfo,
    _ToolPatternTracker,
    _check_env_vars,
    _check_tool_pattern,
    _check_workspace_artifacts,
    _force_detection_from_mode,
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
        assert result.features.has_engram is True
        assert result.features.has_sdd_agents is True
        assert result.features.has_skills is True

    def test_engram_env(self):
        """ENGRAM env var should detect engram orchestrator."""
        with patch.dict(os.environ, {"ENGRAM": "1"}, clear=False):
            result = _check_env_vars()

        assert result is not None
        assert result.is_detected
        assert result.orchestrator_name == "engram"
        assert result.features.has_engram is True

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
        assert result.features.has_skills is True
        assert result.features.has_sdd_agents is True

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
        assert result.features.has_skills is True

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


class TestOrchestratorFeatures:
    """Test OrchestratorFeatures dataclass."""

    def test_orchestrator_features_default_values(self):
        """OrchestratorFeatures should have correct default values."""
        features = OrchestratorFeatures()

        assert features.has_engram is False
        assert features.has_sdd_agents is False
        assert features.has_skills is False
        assert features.has_agent_teams is False
        assert features.detected_tools == []

    def test_orchestrator_features_with_values(self):
        """OrchestratorFeatures should accept custom values."""
        features = OrchestratorFeatures(
            has_engram=True,
            has_sdd_agents=True,
            has_skills=False,
            has_agent_teams=True,
            detected_tools=["mem_save", "sdd-propose"],
        )

        assert features.has_engram is True
        assert features.has_sdd_agents is True
        assert features.has_skills is False
        assert features.has_agent_teams is True
        assert features.detected_tools == ["mem_save", "sdd-propose"]


class TestOrchestratorInfoExpanded:
    """Test OrchestratorInfo with expanded features structure."""

    def test_orchestrator_info_manual_override_default(self):
        """OrchestratorInfo should have manual_override=False by default."""
        info = OrchestratorInfo()
        assert info.manual_override is False

    def test_orchestrator_info_features_is_orchestrator_features(self):
        """OrchestratorInfo.features should be an OrchestratorFeatures instance."""
        info = OrchestratorInfo()
        assert isinstance(info.features, OrchestratorFeatures)

    def test_to_dict_expanded_features(self):
        """to_dict() should return features as expanded dict, not list."""
        info = OrchestratorInfo(
            is_detected=True,
            orchestrator_name="gentle-ai",
            detection_method="tool-pattern:intercept_user_request",
            features=OrchestratorFeatures(
                has_engram=True,
                has_sdd_agents=True,
                has_skills=True,
                has_agent_teams=False,
                detected_tools=["mem_save"],
            ),
            advisor_mode=True,
            manual_override=False,
        )
        d = info.to_dict()

        assert d["is_detected"] is True
        assert d["orchestrator_name"] == "gentle-ai"
        assert d["detection_method"] == "tool-pattern:intercept_user_request"
        assert d["advisor_mode"] is True
        assert d["manual_override"] is False
        # Features should be a dict with individual fields
        assert isinstance(d["features"], dict)
        assert d["features"]["has_engram"] is True
        assert d["features"]["has_sdd_agents"] is True
        assert d["features"]["has_skills"] is True
        assert d["features"]["has_agent_teams"] is False
        assert d["features"]["detected_tools"] == ["mem_save"]


class TestOrchestratorInfoSerialization:
    """Test to_dict() serialization."""

    def test_to_dict_structure(self):
        """to_dict() should return all expected fields with expanded features."""
        info = OrchestratorInfo(
            is_detected=True,
            orchestrator_name="gentle-ai",
            detection_method="env:GENTLE_AI_ACTIVE",
            features=OrchestratorFeatures(has_engram=True, has_sdd_agents=True),
            advisor_mode=True,
            manual_override=False,
        )
        d = info.to_dict()

        assert d["is_detected"] is True
        assert d["orchestrator_name"] == "gentle-ai"
        assert d["advisor_mode"] is True
        assert d["manual_override"] is False
        # Features should be expanded dict
        assert isinstance(d["features"], dict)
        assert d["features"]["has_engram"] is True
        assert d["features"]["has_sdd_agents"] is True


class TestForceDetectionFromMode:
    """Test _force_detection_from_mode() for manual override."""

    def test_force_gentle_ai_mode(self):
        """mode='gentle-ai' should return gentle-ai orchestrator with advisor_mode=True."""
        result = _force_detection_from_mode("gentle-ai")

        assert result is not None
        assert result.is_detected is True
        assert result.orchestrator_name == "gentle-ai"
        assert result.advisor_mode is True
        assert result.manual_override is True

    def test_force_opencode_mode(self):
        """mode='opencode' should return opencode orchestrator."""
        result = _force_detection_from_mode("opencode")

        assert result is not None
        assert result.is_detected is True
        assert result.orchestrator_name == "opencode"
        assert result.manual_override is True

    def test_force_engram_mode(self):
        """mode='engram' should return engram orchestrator with has_engram=True."""
        result = _force_detection_from_mode("engram")

        assert result is not None
        assert result.is_detected is True
        assert result.orchestrator_name == "engram"
        assert result.features.has_engram is True
        assert result.manual_override is True

    def test_force_none_mode(self):
        """mode='none' should return is_detected=False and orchestrator_name='none'."""
        result = _force_detection_from_mode("none")

        assert result is not None
        assert result.is_detected is False
        assert result.orchestrator_name == "none"
        assert result.manual_override is True


class TestToolPatternTracker:
    """Test _ToolPatternTracker class."""

    def test_tracker_initial_state(self):
        """Tracker should have empty signals and calls on init."""
        tracker = _ToolPatternTracker()

        assert tracker.signals == {}
        assert tracker.first_call() is None
        assert tracker.ratio("any_tool") == 0.0

    def test_tracker_record_increments_signal(self):
        """record() should increment the signal count for that tool."""
        tracker = _ToolPatternTracker()

        tracker.record("intercept_user_request")
        tracker.record("intercept_user_request")
        tracker.record("search_context")

        assert tracker.signals["intercept_user_request"] == 2
        assert tracker.signals["search_context"] == 1

    def test_tracker_first_call_returns_first(self):
        """first_call() should return the first recorded tool name."""
        tracker = _ToolPatternTracker()

        tracker.record("search_context")
        tracker.record("intercept_user_request")
        tracker.record("count_tokens")

        assert tracker.first_call() == "search_context"

    def test_tracker_first_call_returns_none_when_empty(self):
        """first_call() should return None when no calls recorded."""
        tracker = _ToolPatternTracker()

        assert tracker.first_call() is None

    def test_tracker_ratio_empty_returns_zero(self):
        """ratio() should return 0.0 when no calls recorded."""
        tracker = _ToolPatternTracker()

        assert tracker.ratio("intercept_user_request") == 0.0

    def test_tracker_ratio_calculates_correctly(self):
        """ratio() should return signal_count / total_calls."""
        tracker = _ToolPatternTracker()

        # Record 3 intercept_user_request out of 10 total calls
        for _ in range(3):
            tracker.record("intercept_user_request")
        for _ in range(7):
            tracker.record("other_tool")

        assert tracker.signals["intercept_user_request"] == 3
        assert len(tracker.signals) == 2
        assert tracker.ratio("intercept_user_request") == 0.3

    def test_tracker_maxlen_sliding_window(self):
        """Tracker should use deque with maxlen for sliding window."""
        tracker = _ToolPatternTracker(maxlen=5)

        # Record 7 calls (should keep only last 5)
        for i in range(7):
            tracker.record(f"tool_{i}")

        # First 2 should be dropped due to maxlen=5
        assert tracker.first_call() == "tool_2"
        assert tracker.signals["tool_0"] == 0  # Dropped
        assert tracker.signals["tool_2"] == 1  # Kept


class TestCheckToolPattern:
    """Test _check_tool_pattern() detection."""

    def test_gentle_ai_with_3_intercept_user_request(self):
        """3+ intercept_user_request calls should detect gentle-ai."""
        tracker = _ToolPatternTracker()
        for _ in range(3):
            tracker.record("intercept_user_request")

        result, guidance = _check_tool_pattern(tracker)

        assert result is not None
        assert result.is_detected is True
        assert result.orchestrator_name == "gentle-ai"
        assert result.detection_method == "tool-pattern:intercept_user_request"
        assert guidance is None

    def test_gentle_ai_with_5_intercept_user_request(self):
        """5 intercept_user_request calls should still detect gentle-ai."""
        tracker = _ToolPatternTracker()
        for _ in range(5):
            tracker.record("intercept_user_request")

        result, guidance = _check_tool_pattern(tracker)

        assert result is not None
        assert result.orchestrator_name == "gentle-ai"

    def test_opencode_with_preflight_first(self):
        """preflight_request as first call should detect opencode."""
        tracker = _ToolPatternTracker()
        tracker.record("preflight_request")
        tracker.record("intercept_user_request")
        tracker.record("search_context")

        result, guidance = _check_tool_pattern(tracker)

        assert result is not None
        assert result.orchestrator_name == "opencode"
        assert result.detection_method == "tool-pattern:preflight_request"
        assert guidance is None

    def test_no_pattern_returns_none(self):
        """No significant pattern should return None with guidance."""
        tracker = _ToolPatternTracker()
        tracker.record("search_context")
        tracker.record("count_tokens")
        tracker.record("index_knowledge")

        result, guidance = _check_tool_pattern(tracker)

        assert result is None
        assert guidance is not None
        assert "No orchestrator detected" in guidance

    def test_get_orchestration_advice_ratio_high(self):
        """High ratio of get_orchestration_advice should return orchestrator."""
        tracker = _ToolPatternTracker()
        # 4 out of 10 calls are get_orchestration_advice (0.4 > 0.3)
        for _ in range(4):
            tracker.record("get_orchestration_advice")
        for _ in range(6):
            tracker.record("other_tool")

        result, guidance = _check_tool_pattern(tracker)

        # Should return some orchestrator based on advice ratio
        assert result is not None
        assert result.is_detected is True
