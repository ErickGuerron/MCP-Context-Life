"""
Governance Helpers — Phase 7 of mcp-context-life-auto-invocation-improvements SDD.

Provides governance and cache health info as plain dicts/text, NOT as Rich renderables.
Integration into existing telemetry views is done by the caller (e.g., cli.py).

Usage:
    from mmcp.presentation.cli.dashboard import get_governance_info
    info = get_governance_info()  # returns dict with cache_status, priority, stale_warning
"""

from __future__ import annotations

import time
from typing import Any, Optional


def get_governance_info() -> Optional[dict[str, Any]]:
    """
    Get governance/health info from AutoInvokeMetrics.

    Returns None if usage_tracking is disabled or if metrics are unavailable.

    Returns a dict with keys:
      - cache_status: "warm" | "cold"
      - governance_priority: "low" | "medium" | "high"
      - is_stale: bool
      - total_invokes: int
      - avg_latency_ms: float
      - tokens_saved: int
    """
    try:
        # Lazy import to allow test patches to take effect
        from mmcp.infrastructure.environment.config import get_config as _get_config

        if not _get_config().usage_tracking_enabled:
            return None

        from mmcp.domain.auto_invoke_metrics import AutoInvokeMetrics

        metrics = AutoInvokeMetrics()
        summary = metrics.get_summary()

        total_invokes = summary.get("total_invokes", 0)
        total_tokens_saved = summary.get("total_tokens_saved", 0)

        # Cache warm/cold
        cache_status = "warm" if total_invokes > 0 else "cold"

        # Governance priority
        if total_invokes > 100:
            priority = "high"
        elif total_invokes > 20:
            priority = "medium"
        else:
            priority = "low"

        # Staleness check
        last_updated = getattr(metrics, "_last_updated", 0)
        now = time.time()
        is_stale = (now - last_updated) > 60 if last_updated else False

        return {
            "cache_status": cache_status,
            "governance_priority": priority,
            "is_stale": is_stale,
            "total_invokes": total_invokes,
            "avg_latency_ms": 0.0,  # computed below if latencies available
            "tokens_saved": total_tokens_saved,
        }
    except Exception:
        return None


def format_governance_lines(info: dict[str, Any]) -> list[str]:
    """
    Format governance info as compact lines for inclusion in telemetry view.

    Output is intentionally minimal — 1-2 lines max to avoid saturating the view.
    Example output:
      - Cache: warm | Priority: medium
      - ⚠ STALE — tracking may be inactive
    """
    lines: list[str] = []

    # Cache + priority on one line
    status = info.get("cache_status", "unknown")
    priority = info.get("governance_priority", "unknown")
    status_color = "green" if status == "warm" else "red"
    priority_color = "red" if priority == "high" else "yellow" if priority == "medium" else "green"
    lines.append(f"Cache: [{status_color}]{status.upper()}[/] | Priority: [{priority_color}]{priority.upper()}[/]")

    # Staleness warning on second line
    if info.get("is_stale"):
        lines.append("[yellow on black]⚠ STALE — tracking may be inactive[/]")

    return lines


def format_governance_rows(info: dict[str, Any]) -> list[tuple[str, str]]:
    """Format governance info as compact telemetry rows for the overview panel."""
    status = info.get("cache_status", "unknown")
    priority = info.get("governance_priority", "unknown")
    status_color = "green" if status == "warm" else "red"
    priority_color = "red" if priority == "high" else "yellow" if priority == "medium" else "green"

    rows: list[tuple[str, str]] = [
        (
            "Governance",
            f"Cache: [{status_color}]{status.upper()}[/] | Priority: [{priority_color}]{priority.upper()}[/]",
        )
    ]

    if info.get("is_stale"):
        rows.append(("Tracking", "[yellow on black]⚠ STALE — tracking may be inactive[/]"))

    return rows
