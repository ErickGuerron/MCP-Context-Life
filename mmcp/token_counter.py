"""
Token Counter Module — Context-Life (CL)

Provides fast, accurate token counting using tiktoken.
Supports multiple encoding schemes and applies a configurable
safety buffer to avoid context window overflows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

import tiktoken

# --- Supported Encodings ---
# cl100k_base  → GPT-4, GPT-3.5-turbo, Claude (close approximation)
# o200k_base   → GPT-4o, GPT-4o-mini
# p50k_base    → Codex, text-davinci
SUPPORTED_ENCODINGS = ("cl100k_base", "o200k_base", "p50k_base")
DEFAULT_ENCODING = "cl100k_base"

# 5% safety buffer — we never fill to the absolute limit
DEFAULT_SAFETY_BUFFER = 0.05


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


def get_encoder(encoding_name: str = DEFAULT_ENCODING) -> tiktoken.Encoding:
    """Get a tiktoken encoder, validated against supported encodings."""
    if encoding_name not in SUPPORTED_ENCODINGS:
        raise ValueError(
            f"Unsupported encoding '{encoding_name}'. "
            f"Supported: {SUPPORTED_ENCODINGS}"
        )
    return tiktoken.get_encoding(encoding_name)


def count_tokens(
    text: str,
    encoding_name: str = DEFAULT_ENCODING,
) -> int:
    """Count the number of tokens in a text string."""
    encoder = get_encoder(encoding_name)
    return len(encoder.encode(text))


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


EncodingName = Literal["cl100k_base", "o200k_base", "p50k_base"]
