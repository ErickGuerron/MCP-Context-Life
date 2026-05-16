"""
Message Normalizer Port — Context-Life (CL)

Defines the interface for message normalization strategies.
Adapters implement this port to provide concrete normalization/denormalization.
"""

from __future__ import annotations

from typing import Protocol


class MessageNormalizerPort(Protocol):
    """
    Port for message normalization strategies.

    Adapters implement this to translate between internal message formats
    and the canonical format used by CacheLoop's _extract_static_prefix.
    """

    def normalize(self, message: dict) -> dict:
        """
        Normalize a message to canonical form.

        Args:
            message: Raw message dict (may contain internal metadata)

        Returns:
            Normalized message with stable field structure
        """
        ...

    def denormalize(self, normalized: dict) -> dict:
        """
        Restore a normalized message to its original form.

        Args:
            normalized: Message in canonical normalized form

        Returns:
            Message with original structure and metadata
        """
        ...
