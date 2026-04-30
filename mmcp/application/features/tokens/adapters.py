from __future__ import annotations

from mmcp.infrastructure.tokens.token_counter import DEFAULT_ENCODING, count_messages_tokens, count_tokens, get_cache_info


class TokenCounterAdapter:
    def count_tokens(self, text: str, encoding_name: str = DEFAULT_ENCODING) -> int:
        return count_tokens(text, encoding_name)

    def count_messages_tokens(self, messages: list[dict], encoding_name: str = DEFAULT_ENCODING) -> int:
        return count_messages_tokens(messages, encoding_name)

    def get_cache_info(self) -> dict:
        return get_cache_info()
