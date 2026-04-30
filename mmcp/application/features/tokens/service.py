from __future__ import annotations

from dataclasses import dataclass, field

from mmcp.application.ports.token_counter import TokenCounterPort
from mmcp.infrastructure.tokens.token_counter import DEFAULT_ENCODING, TokenBudget


@dataclass
class TokenBudgetService:
    token_counter: TokenCounterPort
    budget: TokenBudget = field(default_factory=TokenBudget)

    def count_text(self, text: str, encoding: str = DEFAULT_ENCODING) -> dict:
        token_count = self.token_counter.count_tokens(text, encoding)
        self.budget.consume(token_count)
        return {
            "token_count": token_count,
            "encoding": encoding,
            "budget": self.budget.to_dict(),
        }

    def count_messages(self, messages: list[dict], encoding: str = DEFAULT_ENCODING) -> dict:
        total = self.token_counter.count_messages_tokens(messages, encoding)

        breakdown = []
        for message in messages:
            msg_tokens = self.token_counter.count_messages_tokens([message], encoding)
            breakdown.append(
                {
                    "role": message.get("role", "unknown"),
                    "tokens": msg_tokens,
                    "content_preview": str(message.get("content", ""))[:80],
                }
            )

        self.budget.consume(total)
        return {
            "total_tokens": total,
            "message_count": len(messages),
            "breakdown": breakdown,
            "encoding": encoding,
            "budget": self.budget.to_dict(),
        }

    def reset_budget(self, max_tokens: int = 128_000, safety_buffer: float = 0.05) -> dict:
        self.budget = TokenBudget(max_tokens=max_tokens, safety_buffer=safety_buffer)
        return self.budget.to_dict()

    def budget_snapshot(self) -> dict:
        snapshot = self.budget.to_dict()
        snapshot["token_count_cache"] = self.token_counter.get_cache_info()
        return snapshot
