"""
Trim Orchestrator — Context-Life (CL)

Routes trim requests to the appropriate strategy adapter.
Orchestrates the selection and delegation of trim strategies.

RFC-002: Centralizes trim strategy selection to enable extensible
strategy composition without modifying the public trim_messages API.
"""

from __future__ import annotations

from mmcp.application.ports.trim_strategy import TrimStrategyPort
from mmcp.infrastructure.context.trim_history import DEFAULT_ENCODING, TrimResult
from mmcp.infrastructure.context.trim_strategies.head_strategy import HeadTrimStrategyAdapter
from mmcp.infrastructure.context.trim_strategies.smart_strategy import SmartTrimStrategyAdapter
from mmcp.infrastructure.context.trim_strategies.tail_strategy import TailTrimStrategyAdapter


_STRATEGIES: dict[str, TrimStrategyPort] = {
    "tail": TailTrimStrategyAdapter,
    "head": HeadTrimStrategyAdapter,
    "smart": SmartTrimStrategyAdapter,
}


class TrimOrchestrator:
    """
    Selects and delegates to the appropriate trim strategy.

    Provides a single entry point for all trimming operations,
    routing to the strategy adapter that matches the requested strategy name.
    """

    def __init__(self):
        self._strategies = dict(_STRATEGIES)

    def trim_messages(
        self,
        messages: list[dict],
        max_tokens: int,
        strategy: str = "smart",
        preserve_recent: int = 6,
        encoding: str = DEFAULT_ENCODING,
    ) -> TrimResult:
        """
        Trim messages using the specified strategy.

        Args:
            messages: OpenAI-style message array
            max_tokens: Maximum token budget
            strategy: One of 'tail', 'head', 'smart'
            preserve_recent: (smart only) How many recent messages to protect
            encoding: Tiktoken encoding name

        Returns:
            TrimResult with trimmed messages and diagnostics
        """
        strategy_lower = strategy.lower()
        if strategy_lower not in self._strategies:
            raise ValueError(f"Unknown strategy: {strategy}. Available: {list(self._strategies.keys())}")

        adapter = self._strategies[strategy_lower]

        # Smart strategy takes preserve_recent
        if strategy_lower == "smart":
            return adapter.trim(messages, max_tokens, encoding, preserve_recent=preserve_recent)
        else:
            return adapter.trim(messages, max_tokens, encoding)


# Module-level orchestrator instance
_orchestrator = TrimOrchestrator()


def trim_messages_orchestrated(
    messages: list[dict],
    max_tokens: int,
    strategy: str = "smart",
    preserve_recent: int = 6,
    encoding: str = DEFAULT_ENCODING,
) -> TrimResult:
    """
    Thin wrapper using TrimOrchestrator.

    Preserves the existing module-level trim_messages signature
    while delegating to the strategy adapter pattern.
    """
    return _orchestrator.trim_messages(messages, max_tokens, strategy, preserve_recent, encoding)