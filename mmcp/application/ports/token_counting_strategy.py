"""
Token Counting Strategy Port — Context-Life (CL)

Defines the interface for token counting strategies.
Adapters implement this port to provide concrete token counting behavior.
"""

from __future__ import annotations

from typing import Protocol


class TokenCountingStrategyPort(Protocol):
    """
    Port for token counting strategies.

    Adapters implementing this port provide token counting capabilities
    with optional internal caching and encoder management.
    """

    def count_tokens(self, text: str, encoding: str) -> int:
        """
        Count tokens in a text string.

        Args:
            text: The text to count tokens in
            encoding: Tiktoken encoding name (e.g., 'cl100k_base')

        Returns:
            Token count as an integer
        """
        ...

    def count_messages_tokens(
        self,
        messages: list[dict],
        encoding: str,
    ) -> int:
        """
        Count tokens in an OpenAI-style messages array.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            encoding: Tiktoken encoding name

        Returns:
            Total token count including per-message overhead
        """
        ...

    def get_cache_info(self) -> dict:
        """
        Get LRU cache statistics for diagnostics.

        Returns:
            Dict with hits, misses, maxsize, currsize, hit_rate
        """
        ...