# Delta for fix-context-life-mcp-cached-result-bug

## Problem Statement

**Bug**: `NameError: name '_cached_result' is not defined`

When `cache_context` tool is called (or any tool that invokes `get_orchestration_advice`), the MCP server crashes with `NameError` at `orchestrator_detector.py` line 356.

**Trigger**: Any call to `get_orchestrator_info()` in `mmcp/infrastructure/environment/orchestrator_detector.py` — specifically when `cache_context` or `get_orchestration_advice` tools are invoked.

**Root cause**: Lines 355 and 370 contain `global _cached_result`, but `_cached_result` is never declared at module scope. Python treats undeclared `global` references as NameError at runtime.

## Expected Behavior

When `cache_context` or `get_orchestration_advice` tools are called, the system SHALL:

1. Execute `get_orchestrator_info()` without raising `NameError`
2. Return a cached `OrchestratorInfo` result on subsequent calls
3. Allow `reset_detection()` to clear the cache and reset state

## Verification

### Scenario: cache_context tool executes without error

- GIVEN the MCP server is running
- WHEN `cache_context` tool is invoked
- THEN no `NameError` is raised
- AND the tool returns successfully

### Scenario: get_orchestration_advice executes without error

- GIVEN the MCP server is running
- WHEN `get_orchestration_advice` tool is invoked with valid messages
- THEN no `NameError` is raised
- AND orchestration advice is returned

### Scenario: reset_detection clears cached state

- GIVEN `get_orchestrator_info()` has been called
- WHEN `reset_detection()` is called
- THEN subsequent call to `get_orchestrator_info()` performs fresh detection

### Scenario: Subsequent calls return cached result

- GIVEN `get_orchestrator_info()` has been called
- WHEN `get_orchestration_advice()` is called again
- THEN the cached `OrchestratorInfo` is returned without re-running detection

## Technical Fix

Add module-level declaration in `mmcp/infrastructure/environment/orchestrator_detector.py`:

```python
_cached_result: Optional[OrchestratorInfo] = None
```

This MUST be placed after imports and before any functions that use it (around line 86, adjacent to the `--- Detection Strategies ---` comment).

## Success Criteria

| Criterion | Status |
|-----------|--------|
| `cache_context` tool executes without `NameError` | proposed |
| `get_orchestration_advice` tool executes without `NameError` | proposed |
| `pytest tests/test_context_slice.py -v` passes | proposed |
| `reset_detection()` correctly resets state | proposed |
