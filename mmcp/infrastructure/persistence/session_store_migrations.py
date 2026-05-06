"""DDL migrations adapter for SessionStore."""

from __future__ import annotations

from mmcp.application.ports.session_store_connection import SessionStoreConnectionPort
from mmcp.application.ports.session_store_migrations import SessionStoreMigrationsPort


class SessionStoreMigrations(SessionStoreMigrationsPort):
    """Manages DDL migrations and schema versioning for SessionStore."""

    SCHEMA_VERSION = 1

    def __init__(self, connection: SessionStoreConnectionPort):
        self._connection = connection

    def run_migrations(self) -> None:
        """Run all pending migrations to bring schema up to date."""
        conn = self._connection.get_connection()
        try:
            cursor = conn.cursor()

            # Phase 2: Prefix Cache Ledger (no sensitive prompt payload)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prefix_cache_entries (
                    content_hash TEXT PRIMARY KEY,
                    token_count INTEGER NOT NULL,
                    hits INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    last_hit REAL
                )
            """)

            # Phase 1: Usage Ledger
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    session_id TEXT NOT NULL,
                    host_name TEXT,
                    agent_name TEXT,
                    provider_name TEXT,
                    model_name TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    cached_input_tokens INTEGER,
                    uncached_input_tokens INTEGER,
                    effective_saved_tokens INTEGER,
                    tool_name TEXT,
                    latency_ms REAL
                )
            """)

            # Indexes for faster TUI querying later
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_created ON prefix_cache_entries(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_session ON usage_events(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_host ON usage_events(host_name)")

            conn.commit()
        finally:
            self._connection.close_connection(conn)

    def get_schema_version(self) -> int:
        """Return the current schema version number."""
        return self.SCHEMA_VERSION

    def needs_migration(self) -> bool:
        """Check if there are pending migrations to run."""
        return True  # Always run migrations on init for simplicity
