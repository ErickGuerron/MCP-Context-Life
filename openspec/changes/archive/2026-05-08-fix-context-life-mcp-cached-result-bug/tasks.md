# Tasks: fix-context-life-mcp-cached-result-bug

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 1 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

## Phase 1: Core Fix

- [ ] 1.1 Add `_cached_result: Optional[OrchestratorInfo] = None` at line 86 in `mmcp/infrastructure/environment/orchestrator_detector.py` — place it after line 85 (blank line after `_ToolPatternTracker` class), before the `# --- Detection Strategies ---` comment

## Phase 2: Verification

- [ ] 2.1 Run `pytest tests/test_orchestrator_detector.py tests/test_mcp_status_display.py -v` and confirm all tests pass

## Notes

- This is a one-line fix: Python's `global` requires prior module-level binding; the file already follows this pattern for `_tool_pattern_tracker` at line ~382
- Target line: `mmcp/infrastructure/environment/orchestrator_detector.py` line 86
- No chained PRs needed — single, small PR under 400-line budget