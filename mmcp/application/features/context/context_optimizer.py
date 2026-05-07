"""D4: Context Optimizer — orchestrates the full classification → resolution → pack flow."""

from mmcp.application.features.context.classifiers import (
    ClassificationResult,
    ConflictDetector,
    HaltDetail,
    PromptContextClassifier,
    PromptState,
)
from mmcp.application.features.context.pack_builder import (
    ContextPack,
    ContextPackBuilder,
)
from mmcp.application.features.context.resolver import (
    ContextBudgetManager,
    ProjectContextResolver,
)


class ContextOptimizer:
    """Full flow: classify prompt → detect conflicts → resolve context → build pack."""

    def __init__(self, project_path: str):
        self.classifier = PromptContextClassifier()
        self.conflict_detector = ConflictDetector()
        self.resolver = ProjectContextResolver(project_path)
        self.budget_manager = ContextBudgetManager()
        self.pack_builder = ContextPackBuilder()

    def run(self, request: str, encoding: str = "cl100k_base") -> ContextPack:
        """
        Full flow:
        1. Classify prompt (state + confidence)
        2. Detect conflicts (README vs deps, memory vs code, etc.)
        3. If conflict detected → force CRITICAL with HaltDetail
        4. Resolve project context from Engram + filesystem
        5. Build Context Pack
        6. Return compact JSON
        """
        # Step 1: Classify the prompt
        classification = self.classifier.classify(request)

        # Step 2: Check for critical triggers in the prompt
        halt_detail = None
        conflict_detected = False

        # Check prompt against detected stack for contradiction
        # (In real usage, we'd have resolved project context here)
        prompt_lower = request.lower()
        if any(t in prompt_lower for t in ["javascript", "node", "npm"]):
            # Potential conflict if project uses Python
            detected_stack = self.resolver.resolve(request, ["stack"]).stack
            if detected_stack and detected_stack != ["unknown"]:
                conflict_detected = self.conflict_detector.check_prompt_vs_stack(request, detected_stack)

        # Step 3: Force CRITICAL if conflict detected
        if conflict_detected:
            classification = ClassificationResult(
                state=PromptState.CRITICAL,
                confidence=1.0,
                signals=classification.signals + ["prompt_stack_conflict"],
                reason=f"CONFLICT: Prompt requests different stack than detected ({conflict_detected})",
            )
            halt_detail = HaltDetail(
                detected_goal=[request],
                conflict=["prompt_stack_conflict"],
                risk="CRITICAL",
                required_decision=["Clarify which stack to use: prompt vs project"],
            )

        # Step 4: Resolve project context for missing fields
        missing_context = []
        for field in ["stack", "architecture", "testing", "package_manager"]:
            if field not in classification.signals:
                missing_context.append(field)

        project_context = self.resolver.resolve(request, ["stack", "architecture", "testing", "package_manager"])

        # Step 5: Get context budget based on state and confidence
        context_budget = self.budget_manager.get_budget(classification.state.value, classification.confidence)

        # Step 6: Build the ContextPack
        pack = self.pack_builder.build(
            prompt=request,
            classification=classification,
            project_context=project_context,
            missing_context=missing_context,
            conflict_detected=conflict_detected,
            halt_detail=halt_detail,
        )

        # Set the budget
        pack.context_budget = context_budget

        return pack
