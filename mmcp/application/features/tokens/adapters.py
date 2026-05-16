from __future__ import annotations

from mmcp.infrastructure.tokens.openai_token_counting import OpenAITokenCountingAdapter

# Concrete adapter instance used by TokenBudgetService via TokenCounterPort
_token_counting_adapter = OpenAITokenCountingAdapter()


class TokenCounterAdapter:
    def count_tokens(self, text: str, encoding_name: str = "cl100k_base") -> int:
        return _token_counting_adapter.count_tokens(text, encoding_name)

    def count_messages_tokens(self, messages: list[dict], encoding_name: str = "cl100k_base") -> int:
        return _token_counting_adapter.count_messages_tokens(messages, encoding_name)

    def get_cache_info(self) -> dict:
        return _token_counting_adapter.get_cache_info()
