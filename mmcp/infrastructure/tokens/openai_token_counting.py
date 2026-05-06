"""
OpenAI Token Counting Adapter — Context-Life (CL)

Implements TokenCountingStrategyPort using tiktoken.
Encapsulates LRU caching, encoder caching, and token counting logic.

RFC-002 P2: Moved token counting from token_counter.py module-level functions
into a class adapter to enable interface-based composition.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

import tiktoken

# --- Supported Encodings ---
SUPPORTED_ENCODINGS = ("cl100k_base", "o200k_base", "p50k_base")
DEFAULT_ENCODING = "cl100k_base"

# RFC-002 P2: Minimum string length to cache
_MIN_CACHE_LENGTH = 10

# RFC-002 P2: LRU cache size
_LRU_CACHE_SIZE = 1024


# --- RFC-002 P2: Cached encoder registry ---
_encoder_cache: dict[str, tiktoken.Encoding] = {}


def get_encoder(encoding_name: str) -> tiktoken.Encoding:
    """Get a tiktoken encoder, validated against supported encodings."""
    if encoding_name not in SUPPORTED_ENCODINGS:
        raise ValueError(f"Unsupported encoding '{encoding_name}'. Supported: {SUPPORTED_ENCODINGS}")

    if encoding_name not in _encoder_cache:
        _encoder_cache[encoding_name] = tiktoken.get_encoding(encoding_name)

    return _encoder_cache[encoding_name]


@lru_cache(maxsize=_LRU_CACHE_SIZE)
def _cached_count(text: str, encoding_name: str) -> int:
    """
    LRU-cached token count.
    Uses Python's native hash on the (text, encoding_name) tuple.
    """
    encoder = get_encoder(encoding_name)
    return len(encoder.encode(text))


class OpenAITokenCountingAdapter:
    """
    OpenAI-compatible token counting with LRU caching.

    Implements TokenCountingStrategyPort.
    """

    def count_tokens(self, text: str, encoding: str = DEFAULT_ENCODING) -> int:
        """
        Count tokens in a text string.

        Short strings (<10 chars) bypass the LRU cache to avoid overhead.
        """
        if len(text) < _MIN_CACHE_LENGTH:
            encoder = get_encoder(encoding)
            return len(encoder.encode(text))

        return _cached_count(text, encoding)

    def count_messages_tokens(
        self,
        messages: list[dict],
        encoding: str = DEFAULT_ENCODING,
        tokens_per_message: int = 4,
        tokens_per_name: int = 1,
    ) -> int:
        """
        Count tokens for an OpenAI-style messages array.

        Each message has an overhead of `tokens_per_message` tokens
        plus the content tokens. A final +3 is added for assistant reply priming.
        """
        encoder = get_encoder(encoding)
        total = 0

        for message in messages:
            total += tokens_per_message
            for key, value in message.items():
                if isinstance(value, str):
                    total += len(encoder.encode(value))
                elif isinstance(value, (dict, list)):
                    total += len(encoder.encode(json.dumps(value)))
                if key == "name":
                    total += tokens_per_name

        total += 3
        return total

    def get_cache_info(self) -> dict:
        """Expose LRU cache statistics for diagnostics."""
        info = _cached_count.cache_info()
        return {
            "hits": info.hits,
            "misses": info.misses,
            "maxsize": info.maxsize,
            "currsize": info.currsize,
            "hit_rate": round(info.hits / max(1, info.hits + info.misses) * 100, 2),
        }

    def clear_cache(self) -> None:
        """Clear the LRU token count cache."""
        _cached_count.cache_clear()


EncodingName = Literal["cl100k_base", "o200k_base", "p50k_base"]