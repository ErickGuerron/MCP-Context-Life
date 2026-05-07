# Tasks: mcp-status-scoop-upgrade

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~600-750 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Scoop bucket manifest | PR 1 | New file: `bucket/context-life.json` |
| 2 | MCP status display in tool responses | PR 1 | server.py + cache_manager.py changes |
| 3 | Upgrade error code classification | PR 2 | upgrade.py + new ErrorCode enum + tests |
| 4 | Context Optimization & HALT Governance Layer | PR 3 | 4 new py modules + server.py wiring + unit tests |

---

## Phase 1: Infrastructure (Scoop Manifest)

- [x] 1.1 Create `bucket/` directory
- [x] 1.2 Create `bucket/context-life.json` with version, url, hash, architecture (amd64/arm64), bin fields
- [x] 1.3 Add architecture-specific URLs and SHA256 hashes for latest GitHub release assets
- [x] 1.4 Document bucket URL and installation commands in `openspec/changes/mcp-status-scoop-upgrade/SPEC.md`

---

## Phase 2: Core Implementation — MCP Status Display

- [x] 2.1 In `server.py`: modify `optimize_messages` to append `optimization_status` when `advisor_mode` is True
- [x] 2.2 In `server.py`: modify `cache_context` to append `optimization_status` when `advisor_mode` is True
- [x] 2.3 In `server.py`: modify `intercept_user_request` to append `optimization_status` when `advisor_mode` is True
- [x] 2.4 Define `OptimizationStatus` schema with: strategy, original_tokens, optimized_tokens, messages_modified, resulting_prompt (truncated at 2048 chars)
- [x] 2.5 Add `truncated: true` flag when `resulting_prompt` exceeds 2048 chars

---

## Phase 3: Core Implementation — Upgrade Error Codes

- [ ] 3.1 In `upgrade.py`: create `ErrorCode` enum with: E01 (network), E02 (permission), E03 (PEP 668), E04 (version not found), E05 (checksum), E99 (unknown)
- [ ] 3.2 In `upgrade.py`: create `_parse_upgrade_error(stderr: str) -> ErrorCode` with priority order E03 > E01 > E02 > E04 > E05 > E99
- [ ] 3.3 Replace `_build_failure_panel` generic message with per-code Panel showing code, description, cause, remediation
- [ ] 3.4 For E99 only: include raw stderr in the panel; for others: structured remediation only

---

## Phase 4: Context Optimization & HALT Governance Layer

### 4.1 Signal Constants & Dataclasses

- [ ] 4.1.1 Create `mmcp/application/features/context/classifiers.py` with signal constants: `LIGHT_SIGNALS`, `REQUIRED_SIGNALS`, `CRITICAL_TRIGGERS`
- [ ] 4.1.2 Add `PromptContextClassifier` class with `classify(prompt: str) -> tuple[state, signals]`
- [ ] 4.1.3 Add `compute_confidence(prompt: str, signals: list[str]) -> float` (deterministic per design)
- [ ] 4.1.4 Add `ConflictDetector` with methods: `check_readme_vs_deps()`, `check_memory_vs_code()`, `check_git_vs_structure()`, `check_prompt_vs_stack()`
- [ ] 4.1.5 Add `HaltDetail` and `ContextPack` dataclasses

### 4.2 Resolver & Budget Manager

- [ ] 4.2.1 Create `mmcp/application/features/context/resolver.py` with `ProjectContextResolver` querying Engram, sdd-init, skill-registry, package.json, README.md, git
- [ ] 4.2.2 Add `ContextBudgetManager` mapping state+confidence to tiny/small/medium/full budgets

### 4.3 Context Pack Builder

- [ ] 4.3.1 Create `mmcp/application/features/context/pack_builder.py` with `ContextPackBuilder.build()` returning the required JSON schema
- [ ] 4.3.2 Ensure `halt` field is `null` for LIGHT/REQUIRED, and `HaltDetail` for CRITICAL

### 4.4 Context Optimizer Orchestrator

- [ ] 4.4.1 Create `mmcp/application/features/context/context_optimizer.py` with `ContextOptimizer.run(request)` orchestrating all components
- [ ] 4.4.2 Implement CRITICAL→HALT flow: contradiction forces CRITICAL regardless of confidence score

### 4.5 Server Wiring

- [ ] 4.5.1 Modify `server.py`: `intercept_user_request` delegates to `ContextOptimizer.run(request)`, returns packed JSON instead of the existing flow
- [ ] 4.5.2 Integrate with `get_orchestrator_info().advisor_mode` (existing gate)

---

## Phase 5: Testing

- [ ] 5.1 Write unit tests for `_parse_upgrade_error` covering all 6 error codes and priority order
- [ ] 5.2 Write scenario tests: network failure → E01, permission denied → E02, PEP 668 → E03, etc.
- [ ] 5.3 Test `optimization_status` appears in `optimize_messages` response when `advisor_mode` is True
- [ ] 5.4 Test `optimization_status` is absent when `advisor_mode` is False
- [ ] 5.5 Run `pytest tests/test_upgrade_cli.py` to verify existing upgrade tests still pass
- [ ] 5.6 Write unit tests for `PromptContextClassifier` signal detection
- [ ] 5.7 Write unit tests for `compute_confidence` determinism (same input → same output across N calls)
- [ ] 5.8 Write unit tests for `ConflictDetector` each contradiction type
- [ ] 5.9 Write unit tests for `ContextBudgetManager` tier mapping (tiny/small/medium/full thresholds)
- [ ] 5.10 Write unit tests for `ContextPackBuilder` output shape (all required fields present, types correct)
- [ ] 5.11 Write integration test: full prompt → Context Pack end-to-end
- [ ] 5.12 Write HALT scenario test: CRITICAL contradiction detected, `halt=True`, structured conflict array

---

## Phase 6: Verification

- [ ] 6.1 Run `ruff check mmcp/presentation/cli/upgrade.py mmcp/presentation/mcp/server.py`
- [ ] 6.2 Run `ruff format mmcp/presentation/cli/upgrade.py mmcp/presentation/mcp/server.py`
- [ ] 6.3 Verify all spec scenarios: Scoop install, architecture selection, update detection, advisor mode on/off, error code panels
- [ ] 6.4 Run full pytest suite to confirm no regressions
