# Proposal: fix-context-life-mcp-cached-result-bug

## Intent

Fix a `NameError: name '_cached_result' is not defined` crash in the context-life MCP server that blocks all `cache_context` tool execution. The variable `_cached_result` is used in `get_orchestrator_info()` but never declared as a global or local variable in the module scope.

## Scope

### In Scope
- Declare `_cached_result` at module level in `mmcp/infrastructure/environment/orchestrator_detector.py`
- Add `reset_detection()` call to `initialize_runtime()` to ensure clean state across config changes
- Verify all existing tests pass after fix

### Out of Scope
- Refactoring other global state patterns in the module
- Adding new telemetry or RAG features
- Changes to other MCP tools

## Capabilities

> No new or modified capabilities — pure bug fix. The existing `mcp-status-display` spec behavior is unchanged.

## Approach

**Root cause**: `orchestrator_detector.py` line 356 uses `global _cached_result` inside `get_orchestrator_info()`, but the variable is never declared at module scope. Python treats an undeclared `global` reference as a NameError at runtime.

**Fix**: Add `_cached_result: Optional[OrchestratorInfo] = None` at module level (after imports, before any functions), matching the pattern used for `_tool_pattern_tracker` and all other global state in this file.

The `global _cached_result` declarations at lines 355, 370 already exist — they just have nothing to declare.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `mmcp/infrastructure/environment/orchestrator_detector.py` | Modified | Add `_cached_result` module-level declaration (1 line) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Fix in wrong file | Low | Confirmed via runtime test — error trace shows line 356 |
| Regression in other tools | Low | `get_orchestrator_info()` called by 5+ other tools; fix restores intended behavior |

## Rollback Plan

Revert the single module-level declaration line added. No other files touched.

## Dependencies

- None

## Success Criteria

- [ ] `cache_context` tool executes without `NameError`
- [ ] All existing tests pass (`pytest tests/test_context_slice.py -v`)
- [ ] `get_orchestration_advice` tool still works (uses same orchestrator detection)
