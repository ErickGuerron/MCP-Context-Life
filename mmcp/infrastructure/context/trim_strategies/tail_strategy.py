"""
Tail Trim Strategy — Context-Life (CL)

Implements TrimStrategyPort by keeping the most recent messages
that fit within max_tokens. System messages are preserved at the top.
"""

from __future__ import annotations

from mmcp.application.ports.trim_strategy import TrimStrategyPort
from mmcp.infrastructure.context.trim_history import (
    DEFAULT_ENCODING,
    TrimResult,
)
from mmcp.infrastructure.context.trim_history import (
    trim_tail as original_trim_tail,
)


class TailTrimStrategy:
    """
    Trims to the most recent messages.

    System/developer messages are ALWAYS preserved at the top.
    """

    def trim(
        self,
        messages: list[dict],
        max_tokens: int,
        encoding: str = DEFAULT_ENCODING,
    ) -> TrimResult:
        """
        Keep the most recent messages that fit within max_tokens.

        Args:
            messages: OpenAI-style message array
            max_tokens: Token budget ceiling
            encoding: Tiktoken encoding name

        Returns:
            TrimResult with trimmed messages and diagnostics
        """
        return original_trim_tail(messages, max_tokens, encoding)


# Alias for TrimOrchestrator wiring
TailTrimStrategyAdapter: TrimStrategyPort = TailTrimStrategy()
