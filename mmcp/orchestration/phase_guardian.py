"""
Phase Guardian - Context-Life (CL)

RFC-002 P5: Validates spec exists before SDD apply phase.
Logs to Engram if available, otherwise logs to stderr.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class PhaseGuardianError(Exception):
    """Raised when phase validation fails."""

    def __init__(self, phase: str, reason: str):
        self.phase = phase
        self.reason = reason
        super().__init__(f"Phase '{phase}' validation failed: {reason}")


class PhaseGuardian:
    """Validates phase prerequisites before SDD apply."""

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize PhaseGuardian.

        Args:
            project_root: Project root directory. Defaults to current working directory.
        """
        self._project_root = project_root or Path.cwd()
        self._openspec_dir = self._project_root / "openspec"

    def validate_spec_exists(self, change_name: str) -> bool:
        """Validate that spec.md exists for the given change.

        Args:
            change_name: The name of the change (e.g., 'my-feature').

        Returns:
            True if spec exists, raises PhaseGuardianError otherwise.
        """
        spec_path = self._openspec_dir / "changes" / change_name / "specs" / change_name / "spec.md"

        if not spec_path.exists():
            raise PhaseGuardianError(
                phase="spec",
                reason=f"spec.md not found at {spec_path}. Run 'sdd-spec' before 'sdd-apply'."
            )

        logger.info("PhaseGuardian: spec verified for change '%s'", change_name)
        return True

    def validate_design_exists(self, change_name: str) -> bool:
        """Validate that design.md exists for the given change.

        Args:
            change_name: The name of the change.

        Returns:
            True if design exists, raises PhaseGuardianError otherwise.
        """
        design_path = self._openspec_dir / "changes" / change_name / "design.md"

        if not design_path.exists():
            raise PhaseGuardianError(
                phase="design",
                reason=f"design.md not found at {design_path}. Run 'sdd-design' before 'sdd-apply'."
            )

        logger.info("PhaseGuardian: design verified for change '%s'", change_name)
        return True

    def validate_tasks_exist(self, change_name: str) -> bool:
        """Validate that tasks.md exists for the given change.

        Args:
            change_name: The name of the change.

        Returns:
            True if tasks exist, raises PhaseGuardianError otherwise.
        """
        tasks_path = self._openspec_dir / "changes" / change_name / "tasks.md"

        if not tasks_path.exists():
            raise PhaseGuardianError(
                phase="tasks",
                reason=f"tasks.md not found at {tasks_path}. Run 'sdd-tasks' before 'sdd-apply'."
            )

        logger.info("PhaseGuardian: tasks verified for change '%s'", change_name)
        return True

    def validate_all(self, change_name: str) -> bool:
        """Validate all SDD artifacts exist before apply.

        Args:
            change_name: The name of the change.

        Returns:
            True if all artifacts exist, raises PhaseGuardianError otherwise.
        """
        self.validate_tasks_exist(change_name)
        self.validate_design_exists(change_name)
        self.validate_spec_exists(change_name)
        return True

    def log_to_engram(self, message: str, level: str = "info") -> None:
        """Log message to Engram if available.

        Args:
            message: The message to log.
            level: Log level (info, warning, error).
        """
        # Check if Engram MCP is available via environment
        if os.environ.get("ENGRAM_ACTIVE") == "1":
            # Engram logging would go here if we had the MCP tool
            # For now, just log to standard logger
            if level == "error":
                logger.error("PhaseGuardian: %s", message)
            elif level == "warning":
                logger.warning("PhaseGuardian: %s", message)
            else:
                logger.info("PhaseGuardian: %s", message)
        else:
            # No Engram, just standard logging
            if level == "error":
                logger.error("PhaseGuardian: %s", message)
            elif level == "warning":
                logger.warning("PhaseGuardian: %s", message)
            else:
                logger.info("PhaseGuardian: %s", message)
