# Tasks: mcp-context-life-auto-invocation-improvements

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~700–900 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (infra+cache) → PR 2 (skill+metrics) → PR 3 (persistence+dashboard) → PR 4 (telemetry) |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Infrastructure + Cache Layer | PR 1 | Feature flags, TTL cache, SHA-256 key. Independent foundation. |
| 2 | Skill Enhancement + Metrics | PR 2 | Governance triggers in new skill + async metrics emission. Depends on PR 1 config. |
| 3 | Persistence + Dashboard | PR 3 | SQLite journal, cross-session state, Rich dashboard panel. Independent of PR 2. |
| 4 | Telemetry Integration | PR 4 | Async telemetry bridge to TelemetryService. Depends on PR 1 (cache must exist). |

## Phase 1: Infrastructure (Feature Flags + Config)

- [x] 1.1 Add feature flags to `mmcp/infrastructure/environment/config.py`: `auto_invoke_cache.enabled`, `multi_stack_detection.enabled`, `cross_session_state.enabled`, `governance_dashboard.enabled`, `telemetry.integration.auto_invoke`, `governance.triggers.enabled`, `usage_tracking.enabled`
- [x] 1.2 Add TTL config options: `auto_invoke_cache.ttl_seconds`, `auto_invoke_cache.max_entry_size_bytes`, `cross_session_state.max_state_size_bytes`

## Phase 2: Cache Layer (`mmcp/orchestration/auto_invoke_cache.py`)

- [x] 2.1 RED: Write failing test for `AutoInvokeCache.get()` / `set()` with TTL expiration and SHA-256 key derivation
- [x] 2.2 RED: Write failing test for concurrent deduplication (only one execution for identical concurrent keys)
- [x] 2.3 GREEN: Implement dict-backed LRU cache with TTL, SHA-256 key from `(host, agent, provider, model, operation, args_json)`
- [x] 2.4 GREEN: Implement concurrent request deduplication via `threading.Lock` + waiting threads queue
- [x] 2.5 GREEN: Add `invalidate(key)`, `clear()`, `get_stats()` methods
- [x] 2.6 REFACTOR: Add max entry size guard (skip caching results > 1MB), handle hash collisions with unique entry ID
- [x] 2.7 RED: Write failing test for cache bypass when `auto_invoke_cache.enabled: false`

## Phase 3: Skill Enhancement (`skills/context-life-governance/SKILL.md`)

- [x] 3.1 Create `skills/context-life-governance/SKILL.md` with extended triggers: long-message (>15 msgs), repeated-tool (3+ in window), intent keywords (anxiety, goal-oriented, confusion)
- [x] 3.2 Add trigger config: `governance.triggers.long_message_threshold`, `governance.triggers.repeated_tool_threshold`
- [x] 3.3 Add conversation length tiers (short <10, medium 10–50, long >50) with priority escalation
- [x] 3.4 Add keyword false-positive guard: require 2+ matches before flagging `user_intent`
- [x] 3.5 Add trigger rate limiting: max 1 alert per minute per session

## Phase 4: Usage Metrics (`mmcp/domain/auto_invoke_metrics.py`)

- [x] 4.1 RED: Write failing test for `AutoInvokeMetrics.increment_invokes()` / `record_tokens_saved()` / `record_latency()`
- [x] 4.2 GREEN: Implement `Counter`, `Histogram`, `Gauge` backed by `queue.Queue` for async emission
- [x] 4.3 GREEN: Wire metrics to write to `SessionStore` SQLite ledger (reuse existing telemetry infrastructure)
- [x] 4.4 REFACTOR: Add `get_summary()` returning dict with per-host/per-agent/per-provider/per-model breakdown
- [x] 4.5 Add MCP resource handlers for `usage://overview`, `usage://by-host`, `usage://by-agent` (deferred to PR 3)
- [x] 4.6 RED: Write failing test for `usage_tracking.enabled: false` bypass

## Phase 5: Multi-Stack Detection (`mmcp/infrastructure/environment/orchestrator_detector.py`)

- [x] 5.1 RED: Write failing tests for `_check_multi_stack()` detecting Cursor (`CURSOR_DIR`), Windsurf (`WINDURF_DATA_DIR`), Codex (`codex-cli` process)
- [x] 5.2 GREEN: Add `_check_multi_stack()` method checking env vars and `psutil` process enumeration
- [x] 5.3 REFACTOR: Handle platform differences (Windows `codex-cli.exe` vs Unix `codex-cli`)
- [x] 5.4 Add multi-signal validation: require multiple signals before confirming host
- [x] 5.5 RED: Write failing test for `multi_stack_detection.enabled: false` bypass

## Phase 6: Cross-Session Persistence (`mmcp/infrastructure/persistence/session_persistence.py`)

- [x] 6.1 RED: Write failing test for `SessionPersistence.save_state()` / `load_state()` with atomic writes
- [x] 6.2 GREEN: Implement append-only journal table + state table in `session.db`, atomic writes via SQLite transaction
- [x] 6.3 GREEN: Add `journal_replay()` on startup to reconstruct state
- [x] 6.4 REFACTOR: Add corrupted state archive + fresh start fallback
- [x] 6.5 Add workspace fingerprint persistence (base prefix hash, RAG hash)
- [x] 6.6 RED: Write failing test for `cross_session_state.enabled: false` memory-only mode

## Phase 7: Telemetry Enhancement — Governance Metrics (No Separate Dashboard)

**Approach**: Integrate governance/cache metrics INTO the existing telemetry view
(`_build_telemetry_content()` in `cli.py`) WITHOUT a separate dashboard panel.
Tasteful enhancement — does NOT saturate or damage the existing telemetry view.

Enhancements to add to existing telemetry panels (as compact info lines):
- Cache warm/cold status indicator
- Governance priority tier (low/medium/high)
- Staleness warning if metrics stale >60s
- Auto-invoke count (if usage_tracking_enabled)

- [x] 7.1 RED: Write failing test confirming existing telemetry renders unchanged (no regressions)
- [x] 7.2 GREEN: Add governance info lines to `_build_telemetry_content()` — cache status, priority tier, staleness
- [x] 7.3 REFACTOR: Add governance info to telemetry only when `governance_dashboard.enabled: true`
- [x] 7.4 REFACTOR: Staleness indicator shows only when metrics stale > 60s
- [x] 7.5 GREEN: Add `usage_tracking.enabled: false` graceful bypass — governance lines hidden when tracking off

## Phase 8: Telemetry Integration (`mmcp/infrastructure/telemetry/auto_invoke_tracker.py`)

- [ ] 8.1 RED: Write failing test for `UsageEvent` construction with `event_type="auto_invoke"`, `accounting_mode="derived"`
- [ ] 8.2 GREEN: Implement `auto_invoke_tracker.py` constructing `UsageEvent` and passing to `TelemetryService.log_usage()` via background thread queue
- [ ] 8.3 GREEN: Add queue retry logic when `TelemetryService` unavailable, log warning (not error)
- [ ] 8.4 REFACTOR: Verify overhead < 5ms per invocation
- [ ] 8.5 RED: Write failing test for `telemetry.integration.auto_invoke: false` bypass

## Phase 9: Context Slice Enhancement (`mmcp/domain/context_slice.py` or extend existing)

- [ ] 9.1 RED: Write failing test for `ContextSlice` carrying `cache_key`, `cache_hit`, `ttl_seconds`, `latency_ms`
- [ ] 9.2 GREEN: Extend `ContextSlice` to include cache metadata fields
- [ ] 9.3 GREEN: Add lazy module loading hook for heavy modules on cache miss
- [ ] 9.4 REFACTOR: Add fallback to normal execution when cache entry corrupted

## Phase 10: Integration + Wiring

- [ ] 10.1 Wire `AutoInvokeCache` into auto-invoke execution path, guarded by `auto_invoke_cache.enabled`
- [ ] 10.2 Wire `AutoInvokeMetrics` into cache hit/miss path, guarded by `usage_tracking.enabled`
- [ ] 10.3 Wire `_check_multi_stack()` into `OrchestratorDetector.get_orchestrator_info()`, guarded by `multi_stack_detection.enabled`
- [ ] 10.4 Wire `SessionPersistence` into session lifecycle, guarded by `cross_session_state.enabled`
- [ ] 10.5 Wire dashboard panel into existing TUI render layout, guarded by `governance_dashboard.enabled`
- [ ] 10.6 Wire `auto_invoke_tracker` into auto-invoke completion, guarded by `telemetry.integration.auto_invoke`
