"""SQLite connection adapter for SessionStore."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from mmcp.application.ports.session_store_connection import SessionStoreConnectionPort
from mmcp.infrastructure.environment.config import get_config


class SessionStoreConnection(SessionStoreConnectionPort):
    """Manages SQLite connection lifecycle with thread safety."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            self.db_path: Path = get_config().resolve_cache_db_path()
        else:
            self.db_path = db_path

    def ensure_connection(self) -> None:
        """Ensure the database file and parent directory exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Get a SQLite connection to the database."""
        return sqlite3.connect(
            self.db_path,
            check_same_thread=False,
        )

    def close_connection(self, conn: sqlite3.Connection) -> None:
        """Close a SQLite connection."""
        conn.close()

    def is_connected(self) -> bool:
        """Check if database path is set and accessible."""
        return self.db_path is not None and self.db_path.parent.exists()

    def clear(self) -> None:
        """Clear all data from the database (for testing)."""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM prefix_cache_entries")
            conn.execute("DELETE FROM usage_events")
            conn.commit()
