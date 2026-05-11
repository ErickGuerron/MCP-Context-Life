# Design: fix-context-life-mcp-cached-result-bug

## Fix Location

Add to `mmcp/infrastructure/environment/orchestrator_detector.py` at **line 22** (after the `Optional` import from `typing`):

```python
_cached_result: Optional[OrchestratorInfo] = None
```

Place it alongside the existing module-level state declaration for `_tool_pattern_tracker` (lines 380-385).

## Why Python Requires Prior Declaration

Python's `global` statement does not *create* a variable — it tells Python to assign to the module-level name rather than a local. Without a prior module-level binding, any `global X` + read/write sequence raises `NameError` at runtime.

This differs from JavaScript/PHP where `global $x` implicitly creates if absent. Python requires pre-declaration. The file already follows this pattern correctly for `_tool_pattern_tracker` (line 380) but skipped it for `_cached_result`.

## Existing Tests That Validate This Pattern

| Test | What It Validates |
|------|-------------------|
| `tests/test_orchestrator_detector.py::test_cached_result_reused` (line 199) | Directly manipulates `_cached_result` — variable must exist at module scope |
| `tests/test_orchestrator_detector.py::test_reset_detection` (line 213) | Verifies `reset_detection()` nullifies `_cached_result` |
| `tests/test_mcp_status_display.py` (line 62) | Patches `_cached_result` directly — proves module-level accessibility |

All three tests directly exercise `_cached_result` as a module-level variable, confirming the pattern the fix extends.

## Verification

```bash
pytest tests/test_orchestrator_detector.py tests/test_mcp_status_display.py -v
```

These two test files cover every function in `orchestrator_detector.py` and already validate both the caching behavior and the `global` state access pattern. Once the declaration exists, all tests pass and `cache_context` no longer crashes on import.