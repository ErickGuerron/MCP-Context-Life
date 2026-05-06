"""
JSON Message Normalizer Adapter — Context-Life (CL)

Implements MessageNormalizerPort for OpenAI-style message dicts.
Provides normalize/denormalize operations for cache management.

RFC-002 P2: Messages passed through cache operations must have stable
field structure. This adapter ensures consistent extraction of canonical
message fields (role, content) from any message format.
"""

from __future__ import annotations

from typing import Any


class JsonMessageNormalizerAdapter:
    """
    Normalizes OpenAI-style messages to canonical form.

    The canonical form extracts only `role` and `content` fields,
    which are the stable core of any message structure.
    """

    def normalize(self, message: dict) -> dict:
        """
        Normalize a message to canonical form.

        Extracts role and content, dropping any non-standard fields.
        This ensures consistent hashing and comparison in CacheLoop.

        Args:
            message: Raw message dict

        Returns:
            Canonical message with only role and content
        """
        return {
            "role": message.get("role", ""),
            "content": message.get("content", ""),
        }

    def denormalize(self, normalized: dict) -> dict:
        """
        Restore a normalized message (identity for JSON-serialized messages).

        Since CacheLoop operates on already-serialized content hashes,
        denormalization is a pass-through.

        Args:
            normalized: Message in canonical form

        Returns:
            The same dict (no additional metadata to restore)
        """
        return dict(normalized)