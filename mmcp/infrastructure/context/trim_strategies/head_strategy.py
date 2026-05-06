"""
Head Trim Strategy — Context-Life (CL)

Implements TrimStrategyPort by keeping the oldest messages
that fit within max_tokens. System messages are preserved at the top.
"""

from __future__ import annotations

from mmcp.application.ports.trim_strategy import TrimStrategyPort
from mmcp.infrastructure.context.trim_history import (
    DEFAULT_ENCODING,
    TrimResult,
)
from mmcp.infrastructure.context.trim_history import (
    trim_head as original_trim_head,
)


class HeadTrimStrategy:
    """
    Trims to the oldest messages.

    System/developer messages are ALWAYS preserved at the top.
    """

    def trim(
        self,
        messages: list[dict],
        max_tokens: int,
        encoding: str = DEFAULT_ENCODING,
    ) -> TrimResult:
        """
        Keep the oldest messages that fit within max_tokens.

        Args:
            messages: OpenAI-style message array
            max_tokens: Token budget ceiling
            encoding: Tiktoken encoding name

        Returns:
            TrimResult with trimmed messages and diagnostics
        """
        return original_trim_head(messages, max_tokens, encoding)


# Alias for TrimOrchestrator wiring
HeadTrimStrategyAdapter: TrimStrategyPort = HeadTrimStrategy()
