"""
Orchestrator Detector Module — Context-Life (CL)

RFC-002 P3: Auto-detects when CL is running alongside an AI orchestrator
(e.g., Gentle AI, Engram) to enable "Advisor Mode" — proactive hints
in tool responses about context health and optimization opportunities.

Detection layers:
  1. Environment variables (GENTLE_AI_ACTIVE, ENGRAM, etc.)
  2. Workspace artifacts (.gemini/, .agent/, .agents/)
  3. Process-level hints
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class OrchestratorInfo:
    """Result of orchestrator detection."""

    is_detected: bool = False
    orchestrator_name: str = "none"
    detection_method: str = "none"
    features: list[str] = field(default_factory=list)
    advisor_mode: bool = False

    def to_dict(self) -> dict:
        return {
            "is_detected": self.is_detected,
            "orchestrator_name": self.orchestrator_name,
            "detection_method": self.detection_method,
            "features": self.features,
            "advisor_mode": self.advisor_mode,
        }


# --- Detection Strategies ---

def _check_env_vars() -> Optional[OrchestratorInfo]:
    """Check for orchestrator-specific environment variables."""
    # Gentle AI / Gemini CLI
    if os.environ.get("GENTLE_AI_ACTIVE"):
        return OrchestratorInfo(
            is_detected=True,
            orchestrator_name="gentle-ai",
            detection_method="env:GENTLE_AI_ACTIVE",
            features=["engram", "sdd", "skills"],
            advisor_mode=True,
        )

    # Engram memory system
    if os.environ.get("ENGRAM"):
        return OrchestratorInfo(
            is_detected=True,
            orchestrator_name="engram",
            detection_method="env:ENGRAM",
            features=["persistent_memory", "session_tracking"],
            advisor_mode=True,
        )

    # Generic MCP orchestrator hint
    if os.environ.get("MCP_ORCHESTRATOR"):
        return OrchestratorInfo(
            is_detected=True,
            orchestrator_name=os.environ.get("MCP_ORCHESTRATOR", "unknown"),
            detection_method="env:MCP_ORCHESTRATOR",
            features=["mcp"],
            advisor_mode=True,
        )

    return None


def _check_workspace_artifacts(cwd: Optional[str] = None) -> Optional[OrchestratorInfo]:
    """Check for orchestrator-related workspace artifacts."""
    workspace = Path(cwd) if cwd else Path.cwd()

    # Gentle AI / Gemini CLI artifacts
    gemini_dir = workspace / ".gemini"
    if gemini_dir.is_dir():
        features = ["gemini_config"]
        # Check for specific Gentle AI markers
        if (gemini_dir / "antigravity").is_dir():
            features.extend(["antigravity", "skills", "sdd"])
        return OrchestratorInfo(
            is_detected=True,
            orchestrator_name="gentle-ai",
            detection_method="workspace:.gemini/",
            features=features,
            advisor_mode=True,
        )

    # Agent Teams artifacts
    for agent_dir_name in (".agent", ".agents", "_agent", "_agents"):
        agent_dir = workspace / agent_dir_name
        if agent_dir.is_dir():
            return OrchestratorInfo(
                is_detected=True,
                orchestrator_name="agent-teams",
                detection_method=f"workspace:{agent_dir_name}/",
                features=["workflows", "skills"],
                advisor_mode=True,
            )

    return None


def detect_orchestrator(cwd: Optional[str] = None) -> OrchestratorInfo:
    """
    RFC-002 P3: Detect if an AI orchestrator is present.

    Priority:
      1. Environment variables (explicit, highest confidence)
      2. Workspace artifacts (implicit, medium confidence)

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

    # No orchestrator detected
    return OrchestratorInfo()


# Module-level cached result (detect once per process)
_cached_result: Optional[OrchestratorInfo] = None


def get_orchestrator_info(cwd: Optional[str] = None) -> OrchestratorInfo:
    """
    Get cached orchestrator detection result.

    Detection runs once per process and is cached. Use reset_detection()
    to force re-detection (e.g., in tests).
    """
    global _cached_result
    if _cached_result is None:
        _cached_result = detect_orchestrator(cwd)
    return _cached_result


def reset_detection() -> None:
    """Reset cached detection result (for testing)."""
    global _cached_result
    _cached_result = None
