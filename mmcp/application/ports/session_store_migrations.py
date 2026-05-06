"""Port for SessionStore DDL migrations and schema versioning."""

from __future__ import annotations

from typing import Protocol


class SessionStoreMigrationsPort(Protocol):
    """Manages DDL migrations and schema version tracking."""

    def run_migrations(self) -> None:
        """Run all pending migrations to bring schema up to date."""
        ...

    def get_schema_version(self) -> int:
        """Return the current schema version number."""
        ...

    def needs_migration(self) -> bool:
        """Check if there are pending migrations to run."""
        ...