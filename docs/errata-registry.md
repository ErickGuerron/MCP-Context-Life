# Errata Registry — Context-Life

> Internal registry of bugs, defects, and issues found during development and testing.
> This document is for internal tracking — **not** for public release.
> Each entry documents the identification, root cause, and resolution applied.

---

## ERR-2026-05-15-001: Multi-Stack Detection Test Failure (codex-cli Process Name Mismatch)

**Date Found:** 2026-05-15
**Date Recorded:** 2026-05-15
**Status:** Open (pending fix)
**Severity:** WARNING (non-blocking, pre-existing)
**Change(s) Affected:** `mcp-context-life-auto-invocation-improvements` (Phase 5: Multi-Stack Detection)
**Test:** `tests/test_orchestrator_detector.py::TestMultiStackDetection::test_check_multi_stack_with_all_three_signals`
**Commit Introducing:** `298b067` (attempted fix but introduced platform mismatch)

### Identification

```
FAILED tests/test_orchestrator_detector.py:583: in test_check_multi_stack_with_all_three_signals
    assert "codex" in result.orchestrator_name
E   AssertionError: assert 'codex' in 'cursor-windsurf'
E    +  where 'cursor-windsurf' = OrchestratorInfo(..., orchestrator_name='cursor-windsurf', detection_method='multi-stack:cursor,windsurf'...).orchestrator_name
```

### Summary

Test expects `orchestrator_name` to contain `"codex"` when all three signals (CURSOR_DIR, WINDURF_DATA_DIR, codex-cli process) are present. Actual result: `"cursor-windsurf"` — codex is missing.

### Root Cause

**Platform mismatch in test design.** The test was written with a Linux-centric assumption:

```python
# Test comment says:
# Use cross-platform name (test runs on Linux, codex-cli without .exe)
mock_process.info = {"name": "codex-cli"}
```

However, the test runs on **Windows** (`platform win32`), where the actual process name is `"codex-cli.exe"`, not `"codex-cli"`.

In `_check_multi_stack()` (line 294-295):

```python
is_windows = platform.system() == "Windows"
codex_name = "codex-cli.exe" if is_windows else "codex-cli"
```

The detection logic correctly uses `"codex-cli.exe"` on Windows, but the test mocks the process with `"codex-cli"` — a name that will never match on Windows.

### Detection Flow

1. Test sets env vars: `CURSOR_DIR=/tmp, WINDURF_DATA_DIR=/tmp`
2. Test mocks psutil to return a process with `name: "codex-cli"`
3. `_check_multi_stack()` runs on Windows → looks for `"codex-cli.exe"`
4. Loop: `proc.info["name"] == "codex-cli"` → False (actual name is "codex-cli.exe" but mock has "codex-cli")
5. Codex **not added** to signals list
6. signals = [("cursor", tmp), ("windsurf", tmp)] → 2 signals, `len(signals) >= 2` → passes check
7. Result: `orchestrator_name = "cursor-windsurf"` (missing codex)

### Why Cursor and WindSurf Work

The env vars `CURSOR_DIR` and `WINDURF_DATA_DIR` point to `tempfile.TemporaryDirectory()`, which is a real path that passes `Path(cursor_dir).resolve().exists()`. Both are detected correctly.

### Solution Options

**Option A — Fix the test** (preferred if codex detection on Windows is desired):
Update the test to use the correct platform-specific process name:

```python
import platform
codex_process_name = "codex-cli.exe" if platform.system() == "Windows" else "codex-cli"
mock_process.info = {"name": codex_process_name}
```

**Option B — Fix the code** (if codex detection on Windows is not critical):
Change the matching logic to be more lenient (e.g., substring match `"codex-cli" in proc.info["name"]`).

**Option C — Document as known limitation** (if codex detection on Windows is not required):
The spec requires codex detection, but the test failure is a pre-existing issue that doesn't block functionality since env var detection (cursor/windsurf) still works.

### Evidence

| Check                   | Value                                                     |
| ----------------------- | --------------------------------------------------------- |
| Platform                | Windows (`platform.win32`)                                |
| `codex_name` used       | `"codex-cli.exe"`                                         |
| Mock process name       | `"codex-cli"`                                             |
| Match result            | **False** — codex not detected                            |
| Signals found           | `cursor`, `windsurf` (env vars)                           |
| Signals missing         | `codex` (process)                                         |
| Final orchestrator_name | `"cursor-windsurf"` (expected: `"codex-cursor-windsurf"`) |

### Spec Reference

- **Spec:** `openspec/changes/mcp-context-life-auto-invocation-improvements/specs/multi-stack-detection/spec.md`
- **Requirement:** "Detect Codex via process enumeration (codex-cli or codex-cli.exe)"
- **Phase:** 5 (Multi-Stack Detection), task 5.2

### Notes

- This is a **pre-existing failure** — it existed before the archive and does not block the SDD change completion
- The test passes on Linux (if tests were run there) because `codex_name = "codex-cli"` matches `mock_process.info["name"] = "codex-cli"`
- Only affects the single test `test_check_multi_stack_with_all_three_signals`
- All other 446 tests pass normally

---

## ERR-2026-05-08-001: N+1 Query in Orchestrator Detector

**Date Found:** 2026-05-08
**Date Recorded:** 2026-05-15 (retrospective)
**Status:** Fixed ✅
**Severity:** WARNING (performance)
**File:** `mmcp/infrastructure/environment/orchestrator_detector.py`
**Commit:** `9f29c66`

### Identification

The orchestrator detector was not caching detection results, causing repeated filesystem checks and env var lookups on every call to `get_orchestrator_info()`.

### Root Cause

Missing cache variable at module level. Each call to `get_orchestrator_info()` would re-run all detection strategies (env vars, workspace artifacts, tool patterns) even though the result never changes during a process lifetime.

### Resolution Applied

Added module-level cache:

```python
_cached_result: Optional[OrchestratorInfo] = None
```

And in `get_orchestrator_info()`:

```python
if _cached_result is None:
    _cached_result = detect_orchestrator(cwd)
return _cached_result
```

Added `reset_detection()` function for testing to clear the cache.

### Evidence

| Check      | Value                                                        |
| ---------- | ------------------------------------------------------------ |
| Problem    | N+1 detection calls per session                              |
| Root cause | No caching of OrchestratorInfo                               |
| Fix        | Module-level `_cached_result` singleton                      |
| Test       | `test_orchestrator_detector.py` (all multi-stack tests pass) |

---

## ERR-2026-03-28-001: RAG Search Silent Failure (to_pandas Deprecation)

**Date Found:** 2026-03-28
**Date Recorded:** 2026-05-15 (retrospective)
**Status:** Fixed ✅
**Severity:** CRITICAL (silent data loss)
**File:** `mmcp/rag_engine.py`
**Commit:** `8de68e0`

### Identification

RAG search was silently returning empty results because LanceDB's `to_pandas()` method was being used incorrectly. The method existed but returned data in an unexpected format, causing the iteration to fail silently.

### Root Cause

LanceDB changed API — `to_pandas()` returns a DataFrame but the code was calling `.iterrows()` expecting a structure that didn't match. The iteration would fail silently and return empty results, causing RAG searches to return no context without any error message.

### Resolution Applied

Changed from `to_pandas()` to `to_list()`:

```python
# Before (broken)
results = table.search(query).metric("cosine").limit(top_k).to_pandas()
for _, row in results.iterrows():
    ...

# After (fixed)
rows = table.search(query).metric("cosine").limit(top_k).to_list()
for row in rows:
    ...
```

Also fixed source count tracking and token budget filling logic as part of the same commit.

### Evidence

| Check         | Value                                                   |
| ------------- | ------------------------------------------------------- |
| Problem       | RAG searches returned empty results silently            |
| Root cause    | `to_pandas()` API mismatch with `.iterrows()` usage     |
| Fix           | Changed to `to_list()` which returns plain Python dicts |
| Related fixes | Source count tracking, skip-and-continue budget filling |

---

## ERR-2026-05-05-001: Architecture Refactor Errors (Hexagonal)

**Date Found:** 2026-05-05
**Date Recorded:** 2026-05-15 (retrospective)
**Status:** Fixed ✅
**Severity:** CRITICAL (systemic)
**Files:** Multiple (35 files changed)
**Commit:** `cfff885`

### Identification

During the transition from a flat architecture to hexagonal (ports and adapters), multiple files had import errors, missing port interfaces, and broken dependency injections. The refactor touched 35 files with 1941 insertions and 335 deletions.

### Root Cause

Simultaneous refactor of multiple architectural layers without proper dependency tracking. Ports (interfaces) were defined after adapters (implementations) were already using them, causing circular dependencies and missing implementations.

### Resolution Applied

The commit introduced proper port interfaces:

- `session_store_connection.py` — connection port
- `session_store_queries.py` — query port
- `session_store_row_mapper.py` — row mapping port
- `session_store_migrations.py` — migration port
- `message_normalizer.py` — normalization port
- `token_counting_strategy.py` — counting strategy port
- `trim_strategy.py` — trim strategy port
- `telemetry_store.py` — telemetry port

And properly organized infrastructure adapters:

- `infrastructure/persistence/` — concrete implementations
- `infrastructure/context/` — trim orchestration
- `infrastructure/tokens/` — token counting
- `infrastructure/telemetry/` — telemetry service

### Evidence

| Check            | Value                                                                                          |
| ---------------- | ---------------------------------------------------------------------------------------------- |
| Problem          | 35 files with mixed ports/adapters, circular deps                                              |
| Fix              | Created explicit port interfaces, organized by responsibility                                  |
| Files introduced | 8 new port files, reorganized infrastructure                                                   |
| Test impact      | `tests/conftest.py`, `tests/test_rag_warmup_cli.py`, `tests/test_telemetry_service.py` updated |

---

## ERR-2026-05-05-002: MCP Shim Trigger

**Date Found:** 2026-05-05
**Date Recorded:** 2026-05-15 (retrospective)
**Status:** Fixed ✅
**Severity:** WARNING
**File:** `mmcp/presentation/mcp/server.py`
**Commit:** `fdc7161`

### Identification

The MCP server shim was not correctly triggering the context-life initialization on server startup, causing the auto-invoke context to not be available on first prompt.

### Root Cause

The shim layer between the app container and the MCP server was not properly wiring the context-life components at startup time.

### Resolution Applied

Modified `app_container.py`, `cli.py`, and `server.py` to properly initialize and wire the shim at startup (263 lines added to server.py).

---

## ERR-2026-05-05-003: Telemetry Registration Errors

**Date Found:** 2026-05-05
**Date Recorded:** 2026-05-15 (retrospective)
**Status:** Fixed ✅
**Severity:** WARNING
**Files:** `mmcp/application/features/telemetry/service.py`, `mmcp/infrastructure/telemetry/telemetry_service.py`
**Commit:** `f540883`

### Identification

Telemetry events were not being recorded correctly. The telemetry service had multiple issues:

- `UsageEvent` construction was using wrong field names
- Session store connection was misconfigured
- Message normalization was broken

### Root Cause

During the architecture refactor, telemetry fields were renamed but the service was still using old field names. Also, the connection to `session_store` was broken due to the port/adapter reorganization.

### Resolution Applied

Fixed field names in `UsageEvent` construction and rewired telemetry service to use new port interfaces.

### Evidence

| Check      | Value                                              |
| ---------- | -------------------------------------------------- |
| Problem    | Telemetry not recorded                             |
| Root cause | Field name mismatch + broken port wiring           |
| Fix        | Rewired telemetry service, fixed UsageEvent fields |

---

## ERR-2026-05-10-001: TUI Menu Chrome Inconsistency

**Date Found:** 2026-05-10
**Date Recorded:** 2026-05-15 (retrospective)
**Status:** Fixed ✅
**Severity:** MINOR (UX)
**Files:** `mmcp/presentation/cli/cli.py`
**Commit:** `a066765`

### Identification

TUI menus had inconsistent chrome (headers/footers) — some menus had blank lines between items, others didn't restore the landing chrome properly. In terminals with ≤32 rows, the layout was broken.

### Root Cause

The TUI render logic didn't properly handle:

1. Empty lines between menu items
2. Chrome restoration for all menus/submenus
3. Adaptive body height based on rendered content
4. Compact mode for short terminals

### Resolution Applied

- Removed unnecessary blank lines between menu items
- Added adaptive body height based on content
- Restored landing chrome for all menus/submenus
- Added compact mode for terminals ≤32 rows (reduced spacing, fewer visible rows)
- Added regression test for body height adaptation

### Evidence

| Check   | Value                                                     |
| ------- | --------------------------------------------------------- |
| Problem | Inconsistent TUI chrome, broken layout on short terminals |
| Fix     | Adaptive body height, compact mode, chrome restoration    |
| Tests   | `test_context_life_installer.py` (142 lines added)        |

---

## ERR-2026-05-10-002: APPDATA on Linux CI

**Date Found:** 2026-05-10
**Date Recorded:** 2026-05-15 (retrospective)
**Status:** Fixed ✅
**Severity:** WARNING (CI)
**File:** `mmcp/infrastructure/installation/context_life_installer.py`
**Commit:** `65156f1`

### Identification

VS Code MCP path resolution failed on Linux CI because the code didn't respect `APPDATA` environment variable when set in CI test environments.

### Root Cause

VS Code path resolution on Linux always used `XDG_CONFIG_HOME` or `~/.config`, but CI environments sometimes set `APPDATA` (Windows convention) which was ignored.

### Resolution Applied

Added check for `APPDATA` before falling back to XDG:

```python
# On Linux, respect APPDATA if set (e.g. CI test environment)
appdata = os.environ.get("APPDATA")
if appdata:
    return Path(appdata) / "Code" / "User" / "mcp.json"

# Otherwise use XDG_CONFIG_HOME or ~/.config
xdg = os.environ.get("XDG_CONFIG_HOME")
base = Path(xdg) if xdg else home / ".config"
return base / "Code" / "User" / "mcp.json"
```

### Evidence

| Check       | Value                                      |
| ----------- | ------------------------------------------ |
| Problem     | VS Code path resolution failed on Linux CI |
| Root cause  | APPDATA env var not respected              |
| Fix         | Check APPDATA before XDG fallback          |
| CI verified | Tests pass on Linux CI                     |

---

## ERR-2026-04-30-001: Upgrade Test Assertion Mismatch

**Date Found:** 2026-04-30
**Date Recorded:** 2026-05-15 (retrospective)
**Status:** Fixed ✅
**Severity:** MINOR (test)
**File:** `tests/test_upgrade_cli.py`
**Commit:** `64ee347`

### Identification

Test assertions for upgrade CLI were using wrong expected values after the upgrade flow was refactored.

### Root Cause

The upgrade flow signature changed but the test assertions weren't updated to match the new parameter names and structure.

### Resolution Applied

Fixed assertions:

```python
# Before (wrong)
assert called == [(("v1.2.3", True), {})]

# After (correct)
assert called == [((), {"target_version": "v1.2.3", "dry_run": True, "inside_tui": False})]
```

Also removed an outdated assertion for screen clear codes that changed with the TUI refactor.

### Evidence

| Check   | Value                                                   |
| ------- | ------------------------------------------------------- |
| Problem | Test assertions didn't match actual function signatures |
| Fix     | Updated expected tuples to match actual call signatures |
| Test    | `test_upgrade_cli.py`                                   |

---

## ERR-2026-05-10-003: context-life-advisor Installation Path

**Date Found:** 2026-05-10
**Date Recorded:** 2026-05-15 (retrospective)
**Status:** Fixed ✅
**Severity:** WARNING
**Files:** `mmcp/infrastructure/installation/context_life_installer.py`
**Commit:** `f667b49`, `628333f`

### Identification

The `context-life-advisor` sub-agent was not being correctly written to opencode.json, and model selection wasn't being prompted properly during installation.

### Root Cause

Two related issues:

1. The installer was reading from wrong JSON files (providers vs local models)
2. The agent write operation wasn't completing before the installer returned

### Resolution Applied

- Split provider reading: `auth.json` for API providers, `opencode.json` for local models
- Added proper model selection prompt before agent installation
- Ensured agent is written to opencode.json before confirmation

### Evidence

| Check      | Value                                             |
| ---------- | ------------------------------------------------- |
| Problem    | Advisor not properly installed to opencode.json   |
| Root cause | Wrong config files read, incomplete write         |
| Fix        | Split config reading, proper model selection flow |

---

_Last updated: 2026-05-15_
_Total entries: 10 (1 open, 9 fixed)_
_Next review: ERR-2026-05-15-001 after codex detection resolution decided_
