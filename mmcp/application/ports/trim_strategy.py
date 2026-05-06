"""
Trim Strategy Port — Context-Life (CL)

Defines the interface for message trimming strategies.
Adapters implement this port to provide concrete trimming behavior.
"""

from __future__ import annotations

from typing import Protocol

from mmcp.infrastructure.context.trim_history import TrimResult


class TrimStrategyPort(Protocol):
    """
    Port for message trimming strategies.

    Each adapter implementing this port provides a specific trimming
    algorithm (tail, head, smart, etc.).
    """

    def trim(
        self,
        messages: list[dict],
        max_tokens: int,
        encoding: str,
    ) -> TrimResult:
        """
        Trim a message array to fit within a token budget.

        Args:
            messages: OpenAI-style message array
            max_tokens: Maximum token budget ceiling
            encoding: Tiktoken encoding name

        Returns:
            TrimResult with trimmed messages and diagnostics
        """
        ...