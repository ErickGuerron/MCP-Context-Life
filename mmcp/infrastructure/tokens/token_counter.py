"""
Token Counter Module ΓÇö Context-Life (CL)

Provides fast, accurate token counting using tiktoken.
Supports multiple encoding schemes and applies a configurable
safety buffer to avoid context window overflows.

RFC-002 Improvements:
  - P2: LRU cache for token counts ΓÇö avoids redundant tiktoken calls
  - P2: Cached encoder objects ΓÇö avoids repeated get_encoding() lookups
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

import tiktoken

# --- Supported Encodings ---
# cl100k_base  ΓåÆ GPT-4, GPT-3.5-turbo, Claude (close approximation)
# o200k_base   ΓåÆ GPT-4o, GPT-4o-mini
# p50k_base    ΓåÆ Codex, text-davinci
SUPPORTED_ENCODINGS = ("cl100k_base", "o200k_base", "p50k_base")
DEFAULT_ENCODING = "cl100k_base"

# 5% safety buffer ΓÇö we never fill to the absolute limit
DEFAULT_SAFETY_BUFFER = 0.05

# RFC-002 P2: Minimum string length to cache (avoid overhead for tiny strings)
_MIN_CACHE_LENGTH = 10

# RFC-002 P2: LRU cache size
_LRU_CACHE_SIZE = 1024


@dataclass
class TokenBudget:
    """Tracks token consumption against a configurable limit."""

    max_tokens: int = 128_000
    safety_buffer: float = DEFAULT_SAFETY_BUFFER
    _consumed: int = field(default=0, init=False, repr=False)

    @property
    def effective_limit(self) -> int:
        """Max tokens minus the safety buffer."""
        return int(self.max_tokens * (1 - self.safety_buffer))

    @property
    def consumed(self) -> int:
        return self._consumed

    @property
    def remaining(self) -> int:
        return max(0, self.effective_limit - self._consumed)

    @property
    def usage_percent(self) -> float:
        if self.effective_limit == 0:
            return 100.0
        return round((self._consumed / self.effective_limit) * 100, 2)

    def consume(self, tokens: int) -> None:
        self._consumed += tokens

    def reset(self) -> None:
        self._consumed = 0

    def to_dict(self) -> dict:
        return {
            "max_tokens": self.max_tokens,
            "effective_limit": self.effective_limit,
            "consumed": self.consumed,
            "remaining": self.remaining,
            "usage_percent": self.usage_percent,
            "safety_buffer_percent": self.safety_buffer * 100,
        }


# --- RFC-002 P2: Cached encoder registry ---
_encoder_cache: dict[str, tiktoken.Encoding] = {}


def get_encoder(encoding_name: str = DEFAULT_ENCODING) -> tiktoken.Encoding:
    """
    Get a tiktoken encoder, validated against supported encodings.

    RFC-002 P2: Encoders are cached after first creation to avoid
    repeated tiktoken.get_encoding() calls.
    """
    if encoding_name not in SUPPORTED_ENCODINGS:
        raise ValueError(f"Unsupported encoding '{encoding_name}'. Supported: {SUPPORTED_ENCODINGS}")

    if encoding_name not in _encoder_cache:
        _encoder_cache[encoding_name] = tiktoken.get_encoding(encoding_name)

    return _encoder_cache[encoding_name]


# --- RFC-002 P2: LRU-cached token counting ---


@lru_cache(maxsize=_LRU_CACHE_SIZE)
def _cached_count(text: str, encoding_name: str) -> int:
    """
    LRU-cached token count.

    Uses Python's native hash on the (text, encoding_name) tuple ΓÇö faster
    than SHA-256 and sufficient for an in-process LRU cache.
    """
    encoder = get_encoder(encoding_name)
    return len(encoder.encode(text))


def count_tokens(
    text: str,
    encoding_name: str = DEFAULT_ENCODING,
) -> int:
    """
    Count the number of tokens in a text string.

    RFC-002 P2: Strings >= 10 chars are routed through an LRU cache
    to avoid redundant tiktoken calls during trim_smart's iterative
    enforcement ladder.
    """
    if len(text) < _MIN_CACHE_LENGTH:
        # Short strings ΓÇö direct count, no cache overhead
        encoder = get_encoder(encoding_name)
        return len(encoder.encode(text))

    return _cached_count(text, encoding_name)


def count_messages_tokens(
    messages: list[dict],
    encoding_name: str = DEFAULT_ENCODING,
    tokens_per_message: int = 4,
    tokens_per_name: int = 1,
) -> int:
    """
    Count tokens for an OpenAI-style messages array.

    Each message has an overhead of `tokens_per_message` tokens
    (for role markers, separators, etc.) plus the content tokens.
    A final +3 is added for the assistant reply priming.

    This uses the formula documented by OpenAI for chat models.
    """
    encoder = get_encoder(encoding_name)
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

    total += 3  # assistant reply priming
    return total


def get_cache_info() -> dict:
    """
    RFC-002 P2: Expose LRU cache statistics for diagnostics.

    Returns hit/miss ratio and cache size info.
    """
    info = _cached_count.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "maxsize": info.maxsize,
        "currsize": info.currsize,
        "hit_rate": round(info.hits / max(1, info.hits + info.misses) * 100, 2),
    }


def clear_cache() -> None:
    """RFC-002 P2: Clear the LRU token count cache."""
    _cached_count.cache_clear()


EncodingName = Literal["cl100k_base", "o200k_base", "p50k_base"]
