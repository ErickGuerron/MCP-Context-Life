"""
Smart Trim Strategy — Context-Life (CL)

Implements TrimStrategyPort using the intelligent trimming algorithm
that protects system messages, preserves recent context, and compresses
the middle intelligently.

This is the "crown jewel" strategy of Context-Life.
"""

from __future__ import annotations

from typing import Optional

from mmcp.application.ports.trim_strategy import TrimStrategyPort
from mmcp.infrastructure.context.trim_history import (
    DEFAULT_ENCODING,
    TrimResult,
)
from mmcp.infrastructure.context.trim_history import (
    trim_smart as original_trim_smart,
)


class SmartTrimStrategy:
    """
    Intelligent trimming strategy.

    Strict Budget Enforcement Ladder:
      1. ALWAYS protect system/developer messages when they fit
      2. Try to protect the last `preserve_recent` non-system messages
      3. Drop ALL middle messages first
      4. If still over budget → reduce preserve_recent progressively
      5. If system/developer anchors alone exceed budget → explicit fallback
      6. GUARANTEE: output token count ≤ max_tokens
    """

    def trim(
        self,
        messages: list[dict],
        max_tokens: int,
        encoding: str = DEFAULT_ENCODING,
        preserve_recent: int = 6,
        summary_prompt: Optional[str] = None,
    ) -> TrimResult:
        """
        Intelligently trim messages protecting anchors and recent context.

        Args:
            messages: OpenAI-style message array
            max_tokens: Token budget ceiling
            encoding: Tiktoken encoding name
            preserve_recent: Number of recent non-system messages to protect
            summary_prompt: Optional — reserved for future LLM summarization

        Returns:
            TrimResult with trimmed messages and diagnostics
        """
        return original_trim_smart(
            messages,
            max_tokens,
            preserve_recent=preserve_recent,
            encoding=encoding,
            summary_prompt=summary_prompt,
        )


# Alias for TrimOrchestrator wiring
SmartTrimStrategyAdapter: TrimStrategyPort = SmartTrimStrategy()
