from __future__ import annotations

from typing import Protocol

from mmcp.infrastructure.tokens.token_counter import DEFAULT_ENCODING


class TokenCounterPort(Protocol):
    def count_tokens(self, text: str, encoding_name: str = DEFAULT_ENCODING) -> int: ...

    def count_messages_tokens(self, messages: list[dict], encoding_name: str = DEFAULT_ENCODING) -> int: ...

    def get_cache_info(self) -> dict: ...
