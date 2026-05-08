"""
Orchestrator Detector Module - Context-Life (CL)

RFC-002 P3: Auto-detects when CL is running alongside an AI orchestrator
(e.g., Gentle AI, Engram) to enable "Advisor Mode" - proactive hints
in tool responses about context health and optimization opportunities.

Detection layers:
  1. Environment variables (GENTLE_AI_ACTIVE, ENGRAM, etc.)
  2. Workspace artifacts (.gemini/, .agent/, .agents/)
  3. Process-level hints
"""

from __future__ import annotations

import dataclasses
import os
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_cached_result: Optional[OrchestratorInfo] = None


@dataclass
class OrchestratorFeatures:
    """Detailed feature flags for detected orchestrator."""

    has_engram: bool = False
    has_sdd_agents: bool = False
    has_skills: bool = False
    has_agent_teams: bool = False
    detected_tools: list[str] = field(default_factory=list)


@dataclass
class OrchestratorInfo:
    """Result of orchestrator detection."""

    is_detected: bool = False
    orchestrator_name: str = "none"
    detection_method: str = "none"
    features: OrchestratorFeatures = field(default_factory=OrchestratorFeatures)
    advisor_mode: bool = False
    manual_override: bool = False

    def to_dict(self) -> dict:
        return {
            "is_detected": self.is_detected,
            "orchestrator_name": self.orchestrator_name,
            "detection_method": self.detection_method,
            "features": dataclasses.asdict(self.features),
            "advisor_mode": self.advisor_mode,
            "manual_override": self.manual_override,
        }


class _ToolPatternTracker:
    """Track tool call patterns to infer orchestrator identity."""

    def __init__(self, maxlen: int = 50):
        self._calls = deque(maxlen=maxlen)
        self.signals: dict[str, int] = defaultdict(int)

    def record(self, tool_name: str) -> None:
        """Record a tool call with sliding window."""
        # If deque is full, the item being evicted is no longer in the window
        if len(self._calls) == self._calls.maxlen:
            evicted = self._calls[0]
            self.signals[evicted] -= 1
            if self.signals[evicted] <= 0:
                del self.signals[evicted]
        self._calls.append(tool_name)
        self.signals[tool_name] += 1

    def first_call(self) -> Optional[str]:
        """Return the first recorded tool name, or None if empty."""
        return self._calls[0] if self._calls else None

    def ratio(self, tool_name: str) -> float:
        """Return the ratio of calls for tool_name vs total calls in window."""
        if not self._calls:
            return 0.0
        return self.signals.get(tool_name, 0) / len(self._calls)


# --- Detection Strategies ---


def _force_detection_from_mode(mode: str) -> OrchestratorInfo:
    """Force detection based on config mode (manual override)."""
    if mode == "gentle-ai":
        return OrchestratorInfo(
            is_detected=True,
            orchestrator_name="gentle-ai",
            detection_method=f"config:{mode}",
            features=OrchestratorFeatures(has_engram=True, has_sdd_agents=True, has_skills=True),
            advisor_mode=True,
            manual_override=True,
        )
    elif mode == "opencode":
        return OrchestratorInfo(
            is_detected=True,
            orchestrator_name="opencode",
            detection_method=f"config:{mode}",
            features=OrchestratorFeatures(has_skills=True),
            advisor_mode=False,
            manual_override=True,
        )
    elif mode == "engram":
        return OrchestratorInfo(
            is_detected=True,
            orchestrator_name="engram",
            detection_method=f"config:{mode}",
            features=OrchestratorFeatures(has_engram=True),
            advisor_mode=False,
            manual_override=True,
        )
    elif mode == "none":
        return OrchestratorInfo(
            is_detected=False,
            orchestrator_name="none",
            detection_method=f"config:{mode}",
            features=OrchestratorFeatures(),
            advisor_mode=False,
            manual_override=True,
        )
    # Unknown mode - should not reach here due to validation in load_config
    return OrchestratorInfo(manual_override=True)


def _check_env_vars() -> Optional[OrchestratorInfo]:
    """Check for orchestrator-specific environment variables."""
    # Gentle AI / Gemini CLI
    if os.environ.get("GENTLE_AI_ACTIVE"):
        return OrchestratorInfo(
            is_detected=True,
            orchestrator_name="gentle-ai",
            detection_method="env:GENTLE_AI_ACTIVE",
            features=OrchestratorFeatures(has_engram=True, has_sdd_agents=True, has_skills=True),
            advisor_mode=True,
        )

    # Engram memory system
    if os.environ.get("ENGRAM"):
        return OrchestratorInfo(
            is_detected=True,
            orchestrator_name="engram",
            detection_method="env:ENGRAM",
            features=OrchestratorFeatures(has_engram=True),
            advisor_mode=True,
        )

    # Generic MCP orchestrator hint
    if os.environ.get("MCP_ORCHESTRATOR"):
        return OrchestratorInfo(
            is_detected=True,
            orchestrator_name=os.environ.get("MCP_ORCHESTRATOR", "unknown"),
            detection_method="env:MCP_ORCHESTRATOR",
            features=OrchestratorFeatures(),
            advisor_mode=True,
        )

    return None


def _check_workspace_artifacts(cwd: Optional[str] = None) -> Optional[OrchestratorInfo]:
    """Check for orchestrator-related workspace artifacts."""
    workspace = Path(cwd) if cwd else Path.cwd()

    home_dir = Path.home()
    opencode_roots = (workspace,) if cwd else (workspace, home_dir)

    def _build_detection_method(root: Path, artifact: str) -> str:
        if root == workspace:
            return f"workspace:{artifact}"
        if root == home_dir:
            return f"home:{artifact}"
        return f"path:{artifact}"

    # Gentleman Guardian Angel / Gentle ecosystem marker
    for root in (workspace,):
        gga_file = root / ".gga"
        if gga_file.is_file():
            return OrchestratorInfo(
                is_detected=True,
                orchestrator_name="gentle-ai",
                detection_method=_build_detection_method(root, ".gga"),
                features=OrchestratorFeatures(has_skills=True),
                advisor_mode=True,
            )

    # Gentle AI / Gemini CLI artifacts
    for root in (workspace,):
        gemini_dir = root / ".gemini"
        if gemini_dir.is_dir():
            has_antigravity = (gemini_dir / "antigravity").is_dir()
            return OrchestratorInfo(
                is_detected=True,
                orchestrator_name="gentle-ai",
                detection_method=_build_detection_method(root, ".gemini/"),
                features=OrchestratorFeatures(
                    has_skills=has_antigravity,
                    has_sdd_agents=has_antigravity,
                ),
                advisor_mode=True,
            )

    # OpenCode artifacts - workspace-first, with optional user-config fallback
    for root in opencode_roots:
        opencode_candidates = (
            (root / ".atl", ".atl/", OrchestratorFeatures(has_skills=True)),
            (root / ".opencode", ".opencode/", OrchestratorFeatures()),
            (root / ".config" / "opencode", ".config/opencode/", OrchestratorFeatures()),
        )
        for artifact_path, artifact_name, features in opencode_candidates:
            if artifact_path.is_dir():
                return OrchestratorInfo(
                    is_detected=True,
                    orchestrator_name="opencode",
                    detection_method=_build_detection_method(root, artifact_name),
                    features=features,
                    advisor_mode=True,
                )

    # Agent Teams artifacts
    for root in (workspace,):
        for agent_dir_name in (".agent", ".agents", "_agent", "_agents"):
            agent_dir = root / agent_dir_name
            if agent_dir.is_dir():
                return OrchestratorInfo(
                    is_detected=True,
                    orchestrator_name="agent-teams",
                    detection_method=_build_detection_method(root, f"{agent_dir_name}/"),
                    features=OrchestratorFeatures(has_agent_teams=True, has_skills=True),
                    advisor_mode=True,
                )

    return None


def _check_tool_pattern(tracker: _ToolPatternTracker) -> tuple[Optional[OrchestratorInfo], Optional[str]]:
    """
    Check tool call patterns to infer orchestrator identity.

    Returns:
        Tuple of (OrchestratorInfo or None, guidance message or None)
    """
    # Gentle AI pattern: 3+ intercept_user_request calls
    if tracker.signals.get("intercept_user_request", 0) >= 3:
        return (
            OrchestratorInfo(
                is_detected=True,
                orchestrator_name="gentle-ai",
                detection_method="tool-pattern:intercept_user_request",
                features=OrchestratorFeatures(has_engram=True, has_sdd_agents=True, has_skills=True),
                advisor_mode=True,
            ),
            None,
        )

    # OpenCode pattern: preflight_request as first call
    if tracker.first_call() == "preflight_request":
        return (
            OrchestratorInfo(
                is_detected=True,
                orchestrator_name="opencode",
                detection_method="tool-pattern:preflight_request",
                features=OrchestratorFeatures(has_skills=True),
                advisor_mode=False,
            ),
            None,
        )

    # Active orchestrator pattern: high ratio of get_orchestration_advice
    if tracker.ratio("get_orchestration_advice") > 0.3:
        # Determine orchestrator based on other signals
        has_intercept = tracker.signals.get("intercept_user_request", 0) > 0
        has_engram = tracker.signals.get("mem_save", 0) > 0 or tracker.signals.get("mem_search", 0) > 0

        if has_intercept:
            return (
                OrchestratorInfo(
                    is_detected=True,
                    orchestrator_name="gentle-ai",
                    detection_method="tool-pattern:get_orchestration_advice",
                    features=OrchestratorFeatures(
                        has_engram=has_engram,
                        has_sdd_agents=True,
                        has_skills=True,
                    ),
                    advisor_mode=True,
                ),
                None,
            )
        return (
            OrchestratorInfo(
                is_detected=True,
                orchestrator_name="gentle-ai",
                detection_method="tool-pattern:get_orchestration_advice",
                features=OrchestratorFeatures(has_skills=True),
                advisor_mode=False,
            ),
            None,
        )

    # No pattern detected
    guidance = 'No orchestrator detected. Configure manually in config.toml: [orchestrator] mode = "gentle-ai"'
    return None, guidance


def detect_orchestrator(cwd: Optional[str] = None) -> OrchestratorInfo:
    """
    RFC-002 P3: Detect if an AI orchestrator is present.

    Priority:
      1. Environment variables (explicit, highest confidence)
      2. Workspace artifacts (implicit, medium confidence)
      3. Tool call patterns (inferred, requires session history)

    Args:
        cwd: Working directory to scan for artifacts. Defaults to os.getcwd().

    Returns:
        OrchestratorInfo with detection results
    """
    # Strategy 1: Environment variables
    result = _check_env_vars()
    if result:
        return result

    # Strategy 2: Workspace artifacts
    result = _check_workspace_artifacts(cwd)
    if result:
        return result

    # Strategy 3: Tool call patterns
    tracker = get_tool_pattern_tracker()
    result, _ = _check_tool_pattern(tracker)
    if result:
        return result

    # No orchestrator detected
    return OrchestratorInfo()


def get_orchestrator_info(cwd: Optional[str] = None) -> OrchestratorInfo:
    """
    Get cached orchestrator detection result.

    Detection runs once per process and is cached. Use reset_detection()
    to force re-detection (e.g., in tests).

    Applies config-driven override BEFORE any detection layers.
    """
    global _cached_result
    if _cached_result is None:
        from mmcp.infrastructure.environment.config import get_config

        # Apply config override BEFORE detection layers
        cfg = get_config()
        if cfg.orchestrator_mode != "auto":
            _cached_result = _force_detection_from_mode(cfg.orchestrator_mode)
        else:
            _cached_result = detect_orchestrator(cwd)
    return _cached_result


def reset_detection() -> None:
    """Reset cached detection result (for testing."""
    global _cached_result
    _cached_result = None


def reset_tool_pattern_tracker() -> None:
    """Reset the tool pattern tracker (for testing)."""
    global _tool_pattern_tracker
    _tool_pattern_tracker = None


def get_tool_pattern_tracker() -> _ToolPatternTracker:
    """Get the per-session tool pattern tracker singleton."""
    global _tool_pattern_tracker
    if _tool_pattern_tracker is None:
        _tool_pattern_tracker = _ToolPatternTracker()
    return _tool_pattern_tracker
