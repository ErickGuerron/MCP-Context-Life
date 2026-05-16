"""D4: Project Context Resolution — Engram first, then filesystem fallback."""

from dataclasses import dataclass


@dataclass
class ProjectContext:
    """Resolved project information from Engram memory + filesystem."""

    stack: list[str]
    architecture: str
    testing: str
    package_manager: str


class ContextBudgetManager:
    """Maps state+confidence to token budgets."""

    TINY = "~200 tokens"
    SMALL = "~500 tokens"
    MEDIUM = "~1000 tokens"
    FULL = "no limit"

    def get_budget(self, state: str, confidence: float) -> str:
        """Return budget tier string based on state and confidence."""
        if state == "CRITICAL":
            return self.TINY
        elif state == "LIGHT" and confidence >= 0.90:
            return self.FULL
        elif state == "LIGHT" and confidence >= 0.80:
            return self.SMALL
        elif state == "REQUIRED":
            return self.MEDIUM
        return self.TINY


class ProjectContextResolver:
    """Query Engram first (sdd-init/{project}, skill-registry, recent memory),
    then fall back to package.json, README.md, git diff/log for missing info."""

    def __init__(self, project_path: str):
        self.project_path = project_path

    def resolve(self, prompt: str, missing_info: list[str]) -> ProjectContext:
        """Resolve project context from Engram memory + filesystem."""
        context = {
            "stack": [],
            "architecture": "unknown",
            "testing": "unknown",
            "package_manager": "unknown",
        }

        # Step 1: Try to get from Engram memory (sdd-init/{project}, skill-registry, recent)
        engram_context = self._query_engram()
        for key in ["stack", "architecture", "testing", "package_manager"]:
            if key in missing_info and key in engram_context:
                context[key] = engram_context[key]

        # Step 2: Fallback to filesystem for any remaining missing fields
        if "stack" in missing_info:
            context["stack"] = self._detect_stack_from_filesystem()
        if "architecture" in missing_info:
            context["architecture"] = self._detect_architecture()
        if "testing" in missing_info:
            context["testing"] = self._detect_testing()
        if "package_manager" in missing_info:
            context["package_manager"] = self._detect_package_manager()

        return ProjectContext(**context)

    def _query_engram(self) -> dict:
        """Query Engram memory for project context."""
        # In a real implementation, this would query Engram MCP tools
        # For now, return empty dict to fall through to filesystem
        return {}

    def _detect_stack_from_filesystem(self) -> list[str]:
        """Detect tech stack from package.json, pyproject.toml, go.mod, etc."""
        import json
        import os

        stack = []

        # Check for package.json (Node.js)
        pkg_json = os.path.join(self.project_path, "package.json")
        if os.path.exists(pkg_json):
            try:
                with open(pkg_json, "r", encoding="utf-8") as f:
                    pkg = json.load(f)
                    deps = {}
                    deps.update(pkg.get("dependencies", {}))
                    deps.update(pkg.get("devDependencies", {}))
                    stack.extend(deps.keys())
            except (json.JSONDecodeError, IOError):
                pass

        # Check for pyproject.toml (Python)
        pyproject = os.path.join(self.project_path, "pyproject.toml")
        if os.path.exists(pyproject):
            stack.append("python")

        # Check for go.mod (Go)
        go_mod = os.path.join(self.project_path, "go.mod")
        if os.path.exists(go_mod):
            stack.append("go")

        return stack if stack else ["unknown"]

    def _detect_architecture(self) -> str:
        """Detect architecture from project structure."""
        import os

        # Check for hexagonal/clean architecture markers
        dirs = ["internal", "domain", "application", "infrastructure", "pkg", "src"]
        found = [d for d in dirs if os.path.isdir(os.path.join(self.project_path, d))]
        if "domain" in found and "application" in found and "infrastructure" in found:
            return "hexagonal"
        elif "internal" in found:
            return "layered"
        elif "src" in found:
            return "src-layout"
        return "unknown"

    def _detect_testing(self) -> str:
        """Detect testing framework from project files."""
        import os

        pytest_files = ["pytest.ini", "pyproject.toml", "setup.py", "conftest.py"]
        vitest_files = ["vitest.config.ts", "vitest.config.js"]
        jest_files = ["jest.config.js", "jest.config.ts"]

        for f in pytest_files:
            if os.path.exists(os.path.join(self.project_path, f)):
                return "pytest"
        for f in vitest_files + jest_files:
            if os.path.exists(os.path.join(self.project_path, f)):
                return "jest/vitest"
        if os.path.exists(os.path.join(self.project_path, "go.mod")):
            return "go test"
        return "unknown"

    def _detect_package_manager(self) -> str:
        """Detect package manager from lock files."""
        import os

        lock_files = {
            "package-lock.json": "npm",
            "yarn.lock": "yarn",
            "pnpm-lock.yaml": "pnpm",
            "poetry.lock": "poetry",
            "Pipfile.lock": "pipenv",
            "requirements.txt": "pip",
            "go.mod": "go mod",
            "go.sum": "go mod",
            "Cargo.lock": "cargo",
        }

        for lock_file, pm in lock_files.items():
            if os.path.exists(os.path.join(self.project_path, lock_file)):
                return pm
        return "unknown"
