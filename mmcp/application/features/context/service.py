from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from mmcp.infrastructure.context.trim_history import ContextHealthReport, TrimResult, analyze_context_health, trim_messages
from mmcp.infrastructure.persistence.cache_manager import CacheLoop
from mmcp.infrastructure.tokens.token_counter import DEFAULT_ENCODING


@dataclass
class ContextService:
    cache_loop: CacheLoop = field(default_factory=CacheLoop)

    def optimize_messages(
        self,
        messages: list[dict],
        max_tokens: int,
        strategy: str = "smart",
        preserve_recent: int = 6,
        encoding: str = DEFAULT_ENCODING,
    ) -> TrimResult:
        return trim_messages(messages, max_tokens, strategy, preserve_recent, encoding)

    def cache_context(self, messages: list[dict], rag_context: Optional[str] = None) -> dict:
        return self.cache_loop.process_messages(messages, rag_context=rag_context)

    def analyze_context_health(
        self,
        messages: list[dict],
        max_tokens: int,
        encoding: str = DEFAULT_ENCODING,
    ) -> ContextHealthReport:
        return analyze_context_health(messages, max_tokens, encoding)
