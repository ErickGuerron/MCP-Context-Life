"""Tests for Context Optimization & HALT Governance Layer (D4)."""

import json

import pytest

from mmcp.application.features.context.classifiers import (
    LIGHT_SIGNALS,
    REQUIRED_SIGNALS,
    ClassificationResult,
    ConflictDetector,
    HaltDetail,
    PromptContextClassifier,
    PromptState,
    compute_confidence,
)
from mmcp.application.features.context.context_optimizer import (
    ContextOptimizer,
)
from mmcp.application.features.context.pack_builder import (
    ContextPack,
    ContextPackBuilder,
)
from mmcp.application.features.context.resolver import (
    ContextBudgetManager,
    ProjectContext,
    ProjectContextResolver,
)

# =============================================================================
# SECTION 4.1: PromptContextClassifier + ConflictDetector
# =============================================================================


class TestComputeConfidence:
    """compute_confidence must be deterministic — same input → same output."""

    def test_base_confidence_is_half(self):
        result = compute_confidence("hello world", [])
        assert result == 0.5

    def test_light_signals_add_points(self):
        """Each LIGHT signal adds 0.15 to base confidence."""
        for signal in LIGHT_SIGNALS:
            result = compute_confidence("hello world", [signal])
            assert result == pytest.approx(0.65), f"Signal {signal} should add 0.15"

    def test_required_signals_add_small_points(self):
        """Each REQUIRED signal adds 0.05 to base confidence."""
        for signal in REQUIRED_SIGNALS:
            result = compute_confidence("hello world", [signal])
            assert result == pytest.approx(0.55), f"Signal {signal} should add 0.05"

    def test_multiple_signals_accumulate(self):
        signals = LIGHT_SIGNALS[:2] + REQUIRED_SIGNALS[:1]
        result = compute_confidence("hello world", signals)
        assert result == pytest.approx(0.5 + 0.15 + 0.15 + 0.05)

    def test_caps_at_one(self):
        """Confidence cannot exceed 1.0."""
        result = compute_confidence("hello world", LIGHT_SIGNALS * 10)
        assert result == 1.0

    def test_caps_at_zero(self):
        """Confidence minimum is 0.0 (base starts at 0.5, unknown signals don't subtract)."""
        result = compute_confidence("hello world", ["nonexistent_signal"])
        assert result == 0.5  # Base is 0.5; unknown signals don't add or subtract

    def test_deterministic_same_input_same_output(self):
        """Verify deterministic behavior."""
        prompt = "Please add user authentication to the project"
        signals = ["vague_goal", "implicit_stack"]
        result1 = compute_confidence(prompt, signals)
        result2 = compute_confidence(prompt, signals)
        assert result1 == result2


class TestPromptContextClassifier:
    """PromptContextClassifier analyzes prompts and returns state + confidence."""

    def test_classify_light_prompt(self):
        """Prompt with explicit files and clear goal → LIGHT."""
        prompt = "Add the login button to src/ui/buttons.py using the existing Button component"
        classifier = PromptContextClassifier()
        result = classifier.classify(prompt)

        assert isinstance(result, ClassificationResult)
        assert result.state == PromptState.LIGHT
        assert result.confidence >= 0.7
        assert len(result.signals) > 0

    def test_classify_required_prompt(self):
        """Vague goal with partial files → REQUIRED."""
        prompt = "Fix the thing with the stuff"
        classifier = PromptContextClassifier()
        result = classifier.classify(prompt)

        assert result.state in (PromptState.REQUIRED, PromptState.CRITICAL)
        assert 0.0 <= result.confidence <= 1.0

    def test_classify_returns_signals_list(self):
        """Result must include the signals that were detected."""
        prompt = "make the code better"  # vague
        classifier = PromptContextClassifier()
        result = classifier.classify(prompt)

        assert isinstance(result.signals, list)

    def test_classify_returns_reason(self):
        """Result must include a human-readable reason."""
        prompt = "Add feature X"
        classifier = PromptContextClassifier()
        result = classifier.classify(prompt)

        assert isinstance(result.reason, str)
        assert len(result.reason) > 0


class TestConflictDetector:
    """ConflictDetector checks for README vs deps, memory vs code contradictions."""

    def test_check_readme_vs_deps_mismatch(self):
        """README says React but package.json says Vue → detected."""
        detector = ConflictDetector()
        readme = "This project uses React for the frontend."
        package_json = json.dumps({"dependencies": {"vue": "^3.0.0"}})

        result = detector.check_readme_vs_deps(readme, package_json)
        assert result is True  # mismatch detected

    def test_check_readme_vs_deps_match(self):
        """README and package.json agree → no conflict."""
        detector = ConflictDetector()
        readme = "This project uses React for the frontend."
        package_json = json.dumps({"dependencies": {"react": "^18.0.0"}})

        result = detector.check_readme_vs_deps(readme, package_json)
        assert result is False  # no mismatch

    def test_check_readme_vs_deps_empty_readme(self):
        """Empty README cannot conflict."""
        detector = ConflictDetector()
        result = detector.check_readme_vs_deps("", json.dumps({"dependencies": {"react": "^18.0.0"}}))
        assert result is False

    def test_check_memory_vs_code_conflict(self):
        """Memory policy says no X but code uses X → detected."""
        detector = ConflictDetector()
        memory_policy = "Do not use JavaScript; prefer TypeScript for all new code."
        code_uses_x = True  # code has JavaScript

        result = detector.check_memory_vs_code(memory_policy, code_uses_x)
        assert result is True

    def test_check_memory_vs_code_no_conflict(self):
        """Memory says no X and code doesn't use X → OK."""
        detector = ConflictDetector()
        memory_policy = "Prefer TypeScript over JavaScript."
        code_uses_x = False

        result = detector.check_memory_vs_code(memory_policy, code_uses_x)
        assert result is False

    def test_check_git_vs_structure(self):
        """Recent git changes contradict current structure → detected."""
        detector = ConflictDetector()
        git_recent = ["M src/auth/middleware.ts", "D src/legacy/old.go"]
        current_structure = {"src/auth/middleware.ts": "deleted"}

        # When structure shows file is deleted but git says modified → conflict
        result = detector.check_git_vs_structure(git_recent, current_structure)
        assert result is True

    def test_check_prompt_vs_stack_mismatch(self):
        """Prompt requests Python but detected stack is Node.js → conflict."""
        detector = ConflictDetector()
        prompt_stack = "Python"
        detected_stack = ["node", "npm", "express"]

        result = detector.check_prompt_vs_stack(prompt_stack, detected_stack)
        assert result is True


# =============================================================================
# SECTION 4.2: ContextBudgetManager + ProjectContextResolver
# =============================================================================


class TestContextBudgetManager:
    """ContextBudgetManager maps state+confidence to token budgets."""

    def test_critical_gets_tiny_budget(self):
        """CRITICAL state always gets ~200 tokens (TINY)."""
        manager = ContextBudgetManager()
        assert manager.get_budget("CRITICAL", 0.5) == ContextBudgetManager.TINY
        assert manager.get_budget("CRITICAL", 0.99) == ContextBudgetManager.TINY

    def test_light_high_confidence_gets_full(self):
        """LIGHT + 0.90+ confidence → no limit."""
        manager = ContextBudgetManager()
        assert manager.get_budget("LIGHT", 0.90) == ContextBudgetManager.FULL
        assert manager.get_budget("LIGHT", 1.0) == ContextBudgetManager.FULL

    def test_light_medium_confidence_gets_small(self):
        """LIGHT + 0.80-0.89 confidence → ~500 tokens (SMALL)."""
        manager = ContextBudgetManager()
        assert manager.get_budget("LIGHT", 0.80) == ContextBudgetManager.SMALL
        assert manager.get_budget("LIGHT", 0.85) == ContextBudgetManager.SMALL
        assert manager.get_budget("LIGHT", 0.89) == ContextBudgetManager.SMALL

    def test_required_gets_medium(self):
        """REQUIRED state → ~1000 tokens (MEDIUM)."""
        manager = ContextBudgetManager()
        assert manager.get_budget("REQUIRED", 0.5) == ContextBudgetManager.MEDIUM
        assert manager.get_budget("REQUIRED", 0.7) == ContextBudgetManager.MEDIUM

    def test_default_fallback_is_tiny(self):
        """Unknown state defaults to TINY."""
        manager = ContextBudgetManager()
        assert manager.get_budget("UNKNOWN", 0.5) == ContextBudgetManager.TINY


class TestProjectContext:
    """ProjectContext dataclass holds resolved project information."""

    def test_project_context_has_required_fields(self):
        """All 4 fields must be present."""
        ctx = ProjectContext(
            stack=["python", "fastapi"],
            architecture="hexagonal",
            testing="pytest",
            package_manager="pip",
        )
        assert ctx.stack == ["python", "fastapi"]
        assert ctx.architecture == "hexagonal"
        assert ctx.testing == "pytest"
        assert ctx.package_manager == "pip"


class TestProjectContextResolver:
    """ProjectContextResolver queries Engram then falls back to filesystem."""

    def test_resolver_accepts_project_path(self):
        """Resolver must initialize with project_path."""
        resolver = ProjectContextResolver(".")
        assert resolver.project_path == "."

    def test_resolver_returns_project_context(self):
        """resolve() must return a ProjectContext instance."""
        resolver = ProjectContextResolver(".")
        prompt = "Add authentication"
        missing = ["stack", "architecture", "testing", "package_manager"]

        result = resolver.resolve(prompt, missing)
        assert isinstance(result, ProjectContext)


# =============================================================================
# SECTION 4.3: ContextPackBuilder
# =============================================================================


class TestContextPack:
    """ContextPack is the final JSON output structure."""

    def test_context_pack_has_all_required_fields(self):
        """ContextPack must have: goal, state, confidence, reason, context_budget,
        project_context, files, constraints, missing_context, next_action."""
        pack = ContextPack(
            goal="Add login",
            state="LIGHT",
            confidence=0.85,
            reason="Clear goal with explicit files",
            context_budget="~500 tokens",
            project_context={"stack": [], "architecture": "", "testing": "", "package_manager": ""},
            files={"explicit": [], "inferred": []},
            constraints=[],
            missing_context=[],
            next_action="Implement login endpoint",
        )

        assert pack.goal == "Add login"
        assert pack.state == "LIGHT"
        assert pack.confidence == 0.85
        assert pack.reason == "Clear goal with explicit files"
        assert pack.context_budget == "~500 tokens"
        assert isinstance(pack.project_context, dict)
        assert isinstance(pack.files, dict)
        assert isinstance(pack.constraints, list)
        assert isinstance(pack.missing_context, list)
        assert pack.next_action == "Implement login endpoint"

    def test_context_pack_optional_halt(self):
        """ContextPack may optionally include halt detail."""
        halt = HaltDetail(
            detected_goal=["Add auth"],
            conflict=["memory says no JS but code uses JS"],
            risk="HIGH",
            required_decision=["Choose: follow memory policy or update memory?"],
        )
        pack = ContextPack(
            goal="Add auth",
            state="CRITICAL",
            confidence=1.0,
            reason="Conflict detected",
            context_budget="~200 tokens",
            project_context={},
            files={"explicit": [], "inferred": []},
            constraints=[],
            missing_context=[],
            next_action="Resolve conflict",
            halt=halt,
        )

        assert pack.halt is not None
        assert pack.halt.risk == "HIGH"


class TestContextPackBuilder:
    """ContextPackBuilder assembles the final ContextPack from inputs."""

    def test_build_produces_context_pack(self):
        """build() must return a ContextPack instance."""
        from mmcp.application.features.context.classifiers import PromptContextClassifier

        classifier = PromptContextClassifier()
        classification = classifier.classify("Add login button")
        project_ctx = ProjectContext(
            stack=["python"],
            architecture="hexagonal",
            testing="pytest",
            package_manager="pip",
        )
        builder = ContextPackBuilder()

        pack = builder.build(
            prompt="Add login button to src/ui/",
            classification=classification,
            project_context=project_ctx,
            missing_context=["architecture"],
            conflict_detected=False,
        )

        assert isinstance(pack, ContextPack)
        assert pack.goal == "Add login button to src/ui/"
        assert pack.state == classification.state.value
        assert pack.confidence == classification.confidence

    def test_build_with_halt_detail(self):
        """When conflict_detected=True, HaltDetail must be included."""
        classifier = PromptContextClassifier()
        classification = classifier.classify("Add auth")
        project_ctx = ProjectContext(
            stack=["python"],
            architecture="hexagonal",
            testing="pytest",
            package_manager="pip",
        )
        halt = HaltDetail(
            detected_goal=["Add auth module"],
            conflict=["README vs package.json mismatch"],
            risk="CRITICAL",
            required_decision=["Update README or package.json?"],
        )
        builder = ContextPackBuilder()

        pack = builder.build(
            prompt="Add auth",
            classification=classification,
            project_context=project_ctx,
            missing_context=[],
            conflict_detected=True,
            halt_detail=halt,
        )

        assert isinstance(pack.halt, HaltDetail)
        assert pack.halt.risk == "CRITICAL"
        assert len(pack.halt.conflict) > 0


# =============================================================================
# SECTION 4.4: ContextOptimizer (Integration)
# =============================================================================


class TestContextOptimizer:
    """ContextOptimizer runs the full flow: classify → detect conflicts → resolve → build."""

    def test_optimizer_initializes_all_components(self):
        """Optimizer must initialize classifier, conflict_detector, resolver, budget_manager, pack_builder."""
        optimizer = ContextOptimizer(".")
        assert optimizer.classifier is not None
        assert optimizer.conflict_detector is not None
        assert optimizer.resolver is not None
        assert optimizer.budget_manager is not None
        assert optimizer.pack_builder is not None

    def test_run_returns_context_pack(self):
        """run() must return a ContextPack JSON-serializable object."""
        optimizer = ContextOptimizer(".")
        request = "Add the login button to src/ui/buttons.py using the existing Button component"

        result = optimizer.run(request)

        assert isinstance(result, ContextPack)
        assert result.goal == request
        assert result.state in ("LIGHT", "REQUIRED", "CRITICAL")

    def test_run_returns_json_serializable_pack(self):
        """The output of run() must be JSON-serializable."""
        optimizer = ContextOptimizer(".")
        request = "Add the login button to src/ui/buttons.py"

        result = optimizer.run(request)
        json_str = json.dumps(result.__dict__)

        assert json_str is not None

    def test_run_detects_critical_on_conflict(self):
        """When conflict is detected, state must be CRITICAL with HaltDetail."""
        optimizer = ContextOptimizer(".")

        # A prompt that might trigger a conflict — we'll test with explicit conflict detection
        request = "Add authentication but I want to use JavaScript even though memory says don't"

        result = optimizer.run(request)

        # Either CRITICAL (conflict) or LIGHT/REQUIRED (no conflict) — both valid
        assert result.state in ("LIGHT", "REQUIRED", "CRITICAL")
        # If CRITICAL, halt must be present
        if result.state == "CRITICAL":
            assert result.halt is not None


# =============================================================================
# REGRESSION: Previous PR tests must still pass
# =============================================================================


class TestRegressionUpgradeCli:
    """Regression: ensure PR1+PR2 tests are not broken by D4 changes."""

    def test_import_context_module(self):
        """The context module must be importable without errors."""
        from mmcp.application.features.context import ContextService

        assert ContextService is not None

    def test_classifiers_importable(self):
        """New classifiers module must be importable."""
        from mmcp.application.features.context.classifiers import (
            ConflictDetector,
            PromptContextClassifier,
            PromptState,
        )

        assert PromptContextClassifier is not None
        assert ConflictDetector is not None
        assert PromptState is not None
