"""
Stack Detector Module - Context-Life (CL)

RFC-002 P5: Auto-detects whether CL is running in solo-agent mode
or orchestrator mode to enable appropriate governance.

Detection logic (priority order):
1. DISABLE_AUTOINVOKE=1 → SOLO_AGENT (bypass)
2. ENGRAM_ACTIVE=1 or ENGRAM_SESSION_ID set → ORCHESTRATOR
   (Engram MCP only runs in multi-agent/orchestrator contexts)
3. GENTLE_AI_ACTIVE=1 → ORCHESTRATOR (custom orchestrator override)
4. Otherwise → SOLO_AGENT

Rationale: Engram signals a cross-session memory system that only
orchestrators and multi-agent stacks require. A pure solo-agent
does not activate Engram MCP.
"""

from __future__ import annotations

import os
from enum import Enum


class StackType(Enum):
    SOLO_AGENT = "solo-agent"
    ORCHESTRATOR = "orchestrator"


def detect(cwd: str | None = None) -> StackType:
    """
    Detect the stack type (solo-agent or orchestrator).

    Args:
        cwd: Working directory to scan for artifacts. Defaults to os.getcwd().

    Returns:
        StackType.ORCHESTRATOR if Engram signals, GENTLE_AI_ACTIVE=1,
        or custom orchestrator override; otherwise StackType.SOLO_AGENT.

    Note:
        DISABLE_AUTOINVOKE=1 bypasses detection and always returns SOLO_AGENT.
    """
    # 1. Bypass
    if os.environ.get("DISABLE_AUTOINVOKE") == "1":
        return StackType.SOLO_AGENT

    # 2. Engram signal — active MCP in orchestrator/multi-agent context
    if os.environ.get("ENGRAM_ACTIVE") == "1":
        return StackType.ORCHESTRATOR
    if os.environ.get("ENGRAM_SESSION_ID"):
        return StackType.ORCHESTRATOR

    # 3. Custom orchestrator override
    if os.environ.get("GENTLE_AI_ACTIVE") == "1":
        return StackType.ORCHESTRATOR

    # 4. Default: solo-agent
    return StackType.SOLO_AGENT
