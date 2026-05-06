"""Port for SessionStore connection lifecycle management."""

from __future__ import annotations

import sqlite3
from typing import Protocol


class SessionStoreConnectionPort(Protocol):
    """Manages SQLite connection lifecycle for SessionStore."""

    def get_connection(self) -> sqlite3.Connection:
        """Get a SQLite connection to the database."""
        ...

    def close_connection(self, conn: sqlite3.Connection) -> None:
        """Close a SQLite connection."""
        ...

    def ensure_connection(self) -> None:
        """Ensure the database file and parent directory exist."""
        ...

    def is_connected(self) -> bool:
        """Check if database path is set and accessible."""
        ...
