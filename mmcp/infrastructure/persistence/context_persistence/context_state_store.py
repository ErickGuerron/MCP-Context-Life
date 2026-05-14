"""
Context State Store - Context-Life (CL)

RFC-002 P5: Unified interface for context state persistence.
Supports filesystem adapter for solo-agent and Engram adapter for orchestrator.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Protocol


class ContextStateStore(Protocol):
    """Protocol for context state persistence."""

    def load(self, session_id: str) -> Optional[dict]:
        """Load session state by ID.

        Args:
            session_id: The session identifier.

        Returns:
            Session state dict or None if not found.
        """

    def persist(self, session_id: str, state: dict) -> None:
        """Persist session state.

        Args:
            session_id: The session identifier.
            state: The state dict to persist.
        """

    def delete(self, session_id: str) -> None:
        """Delete session state.

        Args:
            session_id: The session identifier.
        """


class FileSystemAdapter:
    """
    Filesystem adapter for solo-agent mode.

    Persists to: ~/.config/context-life/sessions/{session_id[:16]}/state.json
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        """Initialize the filesystem adapter.

        Args:
            base_dir: Base directory for persistence. Defaults to ~/.config/context-life/sessions.
        """
        if base_dir is None:
            base_dir = Path.home() / ".config" / "context-life" / "sessions"
        self._base_dir = base_dir

    def _session_dir(self, session_id: str) -> Path:
        """Get the session directory for a session ID.

        Uses first 16 chars of session_id as directory name.
        """
        return self._base_dir / session_id[:16]

    def load(self, session_id: str) -> Optional[dict]:
        """Load session state from filesystem."""
        state_file = self._session_dir(session_id) / "state.json"
        if not state_file.exists():
            return None
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def persist(self, session_id: str, state: dict) -> None:
        """Persist session state to filesystem."""
        session_dir = self._session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        state_file = session_dir / "state.json"
        state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    def delete(self, session_id: str) -> None:
        """Delete session state from filesystem."""
        session_dir = self._session_dir(session_id)
        state_file = session_dir / "state.json"
        if state_file.exists():
            state_file.unlink()


def create_context_state_store() -> FileSystemAdapter:
    """Factory function to create a context state store.

    For now, always returns FileSystemAdapter (solo-agent mode).
    Engram adapter can be added when Engram MCP is detected.
    """
    return FileSystemAdapter()
