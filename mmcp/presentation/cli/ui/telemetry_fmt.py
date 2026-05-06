"""Domain layer: cache telemetry statistics formatting.

This module contains pure domain knowledge about how to format
cache usage data into human-readable strings — no UI or I/O.
"""

from __future__ import annotations


def format_big_number(n: int | float) -> str:
    """Format large numbers with K, M, B suffixes."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    elif n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(int(n))


def build_telemetry_summary_lines(
    accounted_input: int, output_tokens: int, saved_tokens: int, budget: int
) -> list[tuple[str, str]]:
    """Build the core telemetry summary panel rows as (label, value) pairs."""
    savings_pct = (saved_tokens / accounted_input * 100) if accounted_input > 0 else 0.0
    return [
        ("Accounted input", format_big_number(accounted_input)),
        ("Output", format_big_number(output_tokens)),
        ("Saved / reused", f"[green]{format_big_number(saved_tokens)}[/]"),
        ("Savings vs input", f"[bold green]{savings_pct:.1f}%[/]"),
    ]


def build_budget_reference_lines(budget: int, tracked_models: int) -> list[tuple[str, str]]:
    """Build the budget reference panel rows as (label, value) pairs."""
    return [
        ("Window", "Rolling 7 days"),
        ("Default request budget", format_big_number(budget)),
        ("Tracked models", str(tracked_models)),
    ]


def build_model_usage_lines(weekly: dict[str, dict[str, int]], max_models: int = 6) -> list[str]:
    """Build per-model usage lines from weekly telemetry data."""
    if not weekly:
        return ["[dim]No usage data for the last 7 days.[/]"]

    sorted_models = sorted(weekly.items(), key=lambda item: item[1]["accounted_input_tokens"], reverse=True)
    lines: list[str] = []
    for model_name, data in sorted_models[:max_models]:
        used = data["accounted_input_tokens"]
        transformed = data["output_tokens"]
        saved = data["saved_tokens"]
        lines.append(
            f"[bold]{model_name}[/] — input {format_big_number(used)} • "
            f"output {format_big_number(transformed)} • saved {format_big_number(saved)}"
        )
    if len(sorted_models) > max_models:
        lines.append(f"[dim]+ {len(sorted_models) - max_models} more model(s) not shown[/]")
    return lines


def build_model_usage_lines_full(weekly: dict[str, dict[str, int]]) -> list[str]:
    """Build all per-model usage lines from weekly telemetry data (no limit)."""
    if not weekly:
        return ["[dim]No usage data for the last 7 days.[/]"]

    sorted_models = sorted(weekly.items(), key=lambda item: item[1]["accounted_input_tokens"], reverse=True)
    lines: list[str] = []
    for model_name, data in sorted_models:
        used = data["accounted_input_tokens"]
        transformed = data["output_tokens"]
        saved = data["saved_tokens"]
        lines.append(
            f"[bold]{model_name}[/] — input {format_big_number(used)} • "
            f"output {format_big_number(transformed)} • saved {format_big_number(saved)}"
        )
    return lines


TELEMETRY_NOTES: list[str] = [
    "Rolling 7-day window recalculates automatically.",
    "Telemetry tracks Context-Life MCP tool calls only, not host LLM billing/cache telemetry.",
    "Input/output/saved now use explicit accounting semantics.",
    "Budget is a per-request reference ceiling, not a weekly quota.",
]
