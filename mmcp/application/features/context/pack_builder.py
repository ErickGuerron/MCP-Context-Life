"""D4: Context Pack Builder — assembles the final ContextPack JSON structure."""

from dataclasses import dataclass
from typing import Optional

from mmcp.application.features.context.classifiers import ClassificationResult, HaltDetail
from mmcp.application.features.context.resolver import ProjectContext


@dataclass
class ContextPack:
    """Final output structure for context optimization."""

    goal: str
    state: str  # "LIGHT" | "REQUIRED" | "CRITICAL"
    confidence: float
    reason: str
    context_budget: str
    project_context: dict  # {stack, architecture, testing, package_manager}
    files: dict  # {explicit: [], inferred: []}
    constraints: list[str]
    missing_context: list[str]
    next_action: str
    halt: Optional[HaltDetail] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "goal": self.goal,
            "state": self.state,
            "confidence": self.confidence,
            "reason": self.reason,
            "context_budget": self.context_budget,
            "project_context": self.project_context,
            "files": self.files,
            "constraints": self.constraints,
            "missing_context": self.missing_context,
            "next_action": self.next_action,
        }
        if self.halt:
            result["halt"] = {
                "detected_goal": self.halt.detected_goal,
                "conflict": self.halt.conflict,
                "risk": self.halt.risk,
                "required_decision": self.halt.required_decision,
            }
        return result


class ContextPackBuilder:
    """Builds the final ContextPack JSON structure from classification + context."""

    def build(
        self,
        prompt: str,
        classification: ClassificationResult,
        project_context: ProjectContext,
        missing_context: list[str],
        conflict_detected: bool = False,
        halt_detail: Optional[HaltDetail] = None,
    ) -> ContextPack:
        """Build the final Context Pack JSON structure."""
        # Extract explicit files from prompt
        explicit_files = self._extract_file_paths(prompt)
        inferred_files = self._infer_related_files(explicit_files)
        constraints = self._extract_constraints(prompt)

        # Determine next action based on state
        next_action = self._determine_next_action(classification.state)

        # Build project context dict
        project_ctx_dict = {
            "stack": project_context.stack,
            "architecture": project_context.architecture,
            "testing": project_context.testing,
            "package_manager": project_context.package_manager,
        }

        return ContextPack(
            goal=prompt,
            state=classification.state.value,
            confidence=classification.confidence,
            reason=classification.reason,
            context_budget="",  # Will be set by budget manager in optimizer
            project_context=project_ctx_dict,
            files={
                "explicit": explicit_files,
                "inferred": inferred_files,
            },
            constraints=constraints,
            missing_context=missing_context,
            next_action=next_action,
            halt=halt_detail,
        )

    def _extract_file_paths(self, prompt: str) -> list[str]:
        """Extract explicit file paths from prompt."""
        import re

        # Match common file path patterns
        path_pattern = r"(?:[a-zA-Z]:)?[\\/]?[a-zA-Z0-9_\-]+[\\/][a-zA-Z0-9_\-./]+"
        matches = re.findall(path_pattern, prompt)
        return [m.strip() for m in matches if "." in m]

    def _infer_related_files(self, explicit_files: list[str]) -> list[str]:
        """Infer related files from explicit files."""
        inferred = []
        for fp in explicit_files:
            # Add adjacent files (e.g., test file for implementation)
            if "/src/" in fp or "\\src\\" in fp:
                # Try to find corresponding test file
                if fp.endswith(".py"):
                    inferred.append(fp.replace("/src/", "/tests/").replace("\\src\\", "\\tests\\"))
                elif fp.endswith(".ts") or fp.endswith(".js"):
                    inferred.append(fp.replace("/src/", "/__tests__/"))
        return inferred

    def _extract_constraints(self, prompt: str) -> list[str]:
        """Extract explicit constraints from prompt."""
        constraints = []
        constraint_keywords = ["using", "with", "must", "should", "require", "limit", "only", "except"]
        prompt_lower = prompt.lower()

        for keyword in constraint_keywords:
            if keyword in prompt_lower:
                idx = prompt_lower.index(keyword)
                # Grab surrounding context
                start = max(0, idx - 20)
                end = min(len(prompt), idx + 60)
                constraints.append(prompt[start:end].strip())

        return constraints

    def _determine_next_action(self, state) -> str:
        """Determine next action based on prompt state."""
        if state.value == "CRITICAL":
            return "HALT: Resolve conflict before proceeding"
        elif state.value == "REQUIRED":
            return "GATHER: Request missing context from user"
        else:
            return "PROCEED: Execute with full context confidence"
