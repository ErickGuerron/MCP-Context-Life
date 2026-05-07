"""D4: Context Optimization — Prompt classifiers and HALT signal detection."""

from dataclasses import dataclass
from enum import Enum

# Signal constants (from design)
LIGHT_SIGNALS = ["clear_goal", "explicit_files", "stack_mentioned", "constraint_listed"]
REQUIRED_SIGNALS = ["vague_goal", "partial_files", "implicit_stack", "loose_constraints"]
CRITICAL_TRIGGERS = [
    "readme_stack_mismatch",
    "memory_policy_conflict",
    "destructive_operation",
    "breaking_public_api",
    "ambiguous_architecture",
]


class PromptState(Enum):
    LIGHT = "LIGHT"
    REQUIRED = "REQUIRED"
    CRITICAL = "CRITICAL"


@dataclass
class ClassificationResult:
    state: PromptState
    confidence: float
    signals: list[str]
    reason: str


@dataclass
class HaltDetail:
    detected_goal: list[str]
    conflict: list[str]
    risk: str
    required_decision: list[str]


class ConflictDetector:
    def check_readme_vs_deps(self, readme_content: str, package_json_content: str) -> bool:
        """Detects README says X but package.json says Y."""
        import json

        if not readme_content.strip():
            return False

        # Extract framework mentions from README
        readme_lower = readme_content.lower()
        frameworks_in_readme = []
        for fw in ["react", "vue", "angular", "svelte", "next", "fastapi", "django", "flask"]:
            if fw in readme_lower:
                frameworks_in_readme.append(fw)

        if not frameworks_in_readme:
            return False

        # Check package.json
        try:
            pkg = json.loads(package_json_content)
            deps = {}
            deps.update(pkg.get("dependencies", {}))
            deps.update(pkg.get("devDependencies", {}))

            [k for k in deps.keys() if any(fw in k.lower() for fw in frameworks_in_readme)]

            # Mismatch: README mentions framework X but package.json has no X dependency
            for fw in frameworks_in_readme:
                if not any(fw in k.lower() for k in deps.keys()):
                    return True
        except (json.JSONDecodeError, AttributeError):
            pass

        return False

    def check_memory_vs_code(self, memory_policy: str, code_uses_x: bool) -> bool:
        """Detects memory says 'don't use X' but code uses X."""
        if not memory_policy:
            return False

        policy_lower = memory_policy.lower()
        # Common "don't use" patterns
        no_js = (
            "don't use javascript" in policy_lower
            or "prefer typescript" in policy_lower
            or "no javascript" in policy_lower
        )
        no_py = "don't use python" in policy_lower or "prefer go" in policy_lower or "no python" in policy_lower

        if no_js and code_uses_x:
            return True
        if no_py and code_uses_x:
            return True

        return False

    def check_git_vs_structure(self, git_recent_changes: list[str], current_structure: dict) -> bool:
        """Detects recent git changes contradict current structure."""
        for change in git_recent_changes:
            if change.startswith("M "):  # Modified
                path = change[2:].strip()
                if path in current_structure:
                    # File shows as deleted in structure but modified in git
                    if current_structure.get(path) == "deleted":
                        return True
            elif change.startswith("D "):  # Deleted
                path = change[2:].strip()
                if path in current_structure:
                    # File shows as present in structure but deleted in git
                    if current_structure.get(path) == "present":
                        return True
        return False

    def check_prompt_vs_stack(self, prompt_stack: str, detected_stack: list[str]) -> bool:
        """Detects prompt requests different stack than detected."""
        if not prompt_stack or not detected_stack:
            return False

        prompt_lower = prompt_stack.lower()
        stack_str = " ".join(detected_stack).lower()

        # Check for direct contradictions
        prompt_js = any(t in prompt_lower for t in ["javascript", "js", "node"])
        prompt_py = any(t in prompt_lower for t in ["python", "py"])
        detected_js = any(t in stack_str for t in ["javascript", "js", "node", "npm"])
        detected_py = any(t in stack_str for t in ["python", "pip", "fastapi"])

        if prompt_py and detected_js:
            return True
        if prompt_js and detected_py:
            return True

        return False


def compute_confidence(prompt: str, signals: list[str]) -> float:
    """Deterministic confidence scoring."""
    base = 0.5
    for signal in signals:
        if signal in LIGHT_SIGNALS:
            base += 0.15
        elif signal in REQUIRED_SIGNALS:
            base += 0.05
    return min(1.0, max(0.0, base))


class PromptContextClassifier:
    def classify(self, prompt: str) -> ClassificationResult:
        """Analyze prompt and return state + confidence."""
        signals = self._extract_signals(prompt)
        confidence = compute_confidence(prompt, signals)
        state = self._determine_state(signals, confidence)
        reason = self._build_reason(prompt, signals, state, confidence)
        return ClassificationResult(
            state=state,
            confidence=confidence,
            signals=signals,
            reason=reason,
        )

    def _extract_signals(self, prompt: str) -> list[str]:
        """Extract signals from prompt text."""
        signals = []
        prompt_lower = prompt.lower()

        # LIGHT signals
        if self._has_explicit_files(prompt):
            signals.append("explicit_files")
        if self._has_clear_goal(prompt):
            signals.append("clear_goal")
        if any(k in prompt_lower for k in ["stack", "tech", "framework", "python", "javascript"]):
            signals.append("stack_mentioned")
        if self._has_constraints(prompt):
            signals.append("constraint_listed")

        # REQUIRED signals
        if self._is_vague(prompt):
            signals.append("vague_goal")
        if not self._has_explicit_files(prompt):
            signals.append("partial_files")
        if not any(k in prompt_lower for k in ["stack", "tech", "framework", "python", "javascript"]):
            signals.append("implicit_stack")
        if not self._has_constraints(prompt):
            signals.append("loose_constraints")

        return signals

    def _has_explicit_files(self, prompt: str) -> bool:
        """Check for explicit file paths."""
        indicators = ["/", ".py", ".ts", ".js", ".go", ".rs", "src/", "internal/", "pkg/"]
        return any(ind in prompt for ind in indicators)

    def _has_clear_goal(self, prompt: str) -> bool:
        """Check for clear, specific goal language."""
        vague_words = ["something", "stuff", "thing", "update", "fix", "improve", "better"]
        prompt_lower = prompt.lower()
        has_vague = any(w in prompt_lower for w in vague_words)
        # Short vague prompts are likely REQUIRED
        if has_vague and len(prompt.split()) < 10:
            return False
        return not has_vague

    def _has_constraints(self, prompt: str) -> bool:
        """Check for explicit constraints."""
        constraint_indicators = ["using", "with", "must", "should", "require", "limit", "only"]
        return any(ind in prompt.lower() for ind in constraint_indicators)

    def _is_vague(self, prompt: str) -> bool:
        """Check if prompt is vague."""
        vague_patterns = [
            "fix it",
            "make it better",
            "update stuff",
            "add thing",
            "some feature",
            "improve code",
            "clean up",
            "refactor something",
        ]
        prompt_lower = prompt.lower().strip()
        return any(p in prompt_lower for p in vague_patterns) or len(prompt.split()) < 5

    def _determine_state(self, signals: list[str], confidence: float) -> PromptState:
        """Determine state from signals and confidence."""
        critical_count = sum(1 for s in signals if s in CRITICAL_TRIGGERS)
        if critical_count > 0:
            return PromptState.CRITICAL

        light_count = sum(1 for s in signals if s in LIGHT_SIGNALS)
        required_count = sum(1 for s in signals if s in REQUIRED_SIGNALS)

        if light_count > required_count and confidence >= 0.80:
            return PromptState.LIGHT
        elif required_count > light_count or confidence < 0.55:
            return PromptState.REQUIRED
        else:
            return PromptState.REQUIRED

    def _build_reason(self, prompt: str, signals: list[str], state: PromptState, confidence: float) -> str:
        """Build human-readable reason."""
        if state == PromptState.LIGHT:
            return f"Clear goal with {len(signals)} signal(s), confidence {confidence:.2f}"
        elif state == PromptState.CRITICAL:
            return f"CRITICAL: {len(signals)} conflicting signal(s) detected, confidence {confidence:.2f}"
        else:
            return f"REQUIRED: ambiguous prompt with {len(signals)} signal(s), confidence {confidence:.2f}"
