# Design: mcp-context-life-auto-invocation-improvements

## Technical Approach

Implement seven incremental improvements to the auto-invoke subsystem: TTL cache, skill trigger enrichment, usage metrics, multi-stack detection, SQLite cross-session persistence, a Rich-based governance TUI panel, and async telemetry bridge. All components follow the existing hexagonal/port-adapter structure and reuse `SessionStore` SQLite infrastructure.

## Architecture Decisions

### Decision: In-memory TTL cache with SHA-256 key derivation

**Choice**: `mmcp/orchestration/auto_invoke_cache.py` — dict-backed LRU cache with TTL, SHA-256 key from `(host, agent, provider, model, operation, args_json)`.
**Alternatives**: Redis/external cache (overkill for local-MCP), SQLite-based cache (adds latency per lookup).
**Rationale**: Auto-invoke deduplication must be sub-millisecond; in-process dict is fastest. TTL + LRU eviction prevents unbounded memory growth. Config flag `auto_invoke_cache.enabled` gates the entire layer.

### Decision: Async metrics emission via queue

**Choice**: `mmcp/domain/auto_invoke_metrics.py` — `Counter`, `Histogram`, `Gauge` backed by `SessionStore` SQLite ledger, emitted async via `queue.Queue`.
**Alternatives**: Blocking inline emit (adds latency), external metrics aggregator (new dependency).
**Rationale**: Non-blocking emission keeps the invoke path fast. SQLite already persists all telemetry — the metrics module writes to the same ledger.

### Decision: Stack detection appends to existing `OrchestratorInfo` chain

**Choice**: Extend `mmcp/infrastructure/environment/orchestrator_detector.py` with `_check_multi_stack()` — checks `CURSOR_DIR`, `WINDURF_DATA_DIR`, and `psutil` for `codex-cli`.
**Alternatives**: Separate `StackDetector` class (duplicates detection infrastructure), detection-as-tool (mixed concerns).
**Rationale**: Orchestrator detection already has env-var, artifact, and tool-pattern layers. Multi-stack detection is a new env-var/process layer that composes naturally. Config flag `multi_stack_detection.enabled` gates it.

### Decision: Cross-session state via SQLite journal

**Choice**: `mmcp/infrastructure/persistence/session_persistence.py` — append-only journal table + state table in `session.db`. Atomic writes via SQLite transaction. On startup, replay journal to reconstruct state.
**Alternatives**: JSON file (no crash recovery), separate SQLite file (additional connection overhead).
**Rationale**: Reuses existing `SessionStore` SQLite connection. Journal enables crash recovery without distributed locking. Config flag `cross_session_state.enabled` gates it.

### Decision: Rich-based dashboard panel (not textual)

**Choice**: `mmcp/presentation/cli/dashboard.py` — single-pass `Panel` render using existing `rich` infrastructure from `render.py`. No separate event loop.
**Alternatives**: `textual` (new framework, heavier), live-updating terminal (complex state management).
**Rationale**: `render.py` already uses Rich. Adding a governance panel to the existing TUI layout is lightweight. Dashboard shows: session age, context token count vs budget, cache warm/cold, invoke count, last save, active triggers, governance priority.

### Decision: Telemetry bridge via existing `TelemetryService`

**Choice**: `mmcp/infrastructure/telemetry/auto_invoke_tracker.py` — constructs `UsageEvent(event_type="auto_invoke", accounting_mode="derived", ...)` and passes to `TelemetryService.log_usage()`. Async via background thread queue.
**Alternatives**: Separate telemetry pipeline (code duplication), inline emit (latency hit).
**Rationale**: Existing `TelemetryService` handles persistence, error handling, and schema. Bridge module only translates auto-invoke specifics and queues the async emit. Config flag `telemetry.integration.auto_invoke` gates it.

## Data Flow

### Cache Flow
```
Auto-invoke request
  → SHA-256(cache_key)
  → Check in-memory cache dict
      HIT → return cached result + metrics
      MISS → execute operation
             → store result with TTL
             → async metrics emit
```

### Dashboard Flow
```
SessionStore.get_cache_stats() + metrics query
  → dashboard panel render (Rich)
  → TTY output via existing render layout
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `mmcp/orchestration/auto_invoke_cache.py` | Create | TTL cache, SHA-256 key, LRU eviction, dedup concurrent requests |
| `mmcp/domain/auto_invoke_metrics.py` | Create | Counter/Histogram/Gauge for invokes, tokens saved, latency |
| `mmcp/infrastructure/persistence/session_persistence.py` | Create | SQLite journal + state table, atomic writes, crash recovery |
| `mmcp/infrastructure/telemetry/auto_invoke_tracker.py` | Create | Async UsageEvent bridge to TelemetryService |
| `mmcp/infrastructure/environment/orchestrator_detector.py` | Modify | Add `_check_multi_stack()` for cursor/windsurf/codex |
| `mmcp/presentation/cli/dashboard.py` | Create | Rich panel: session health, cache metrics, governance status |
| `skills/context-life-governance/SKILL.md` | Modify | Add triggers: long-msg (>15), repeated-tool (3+), intent keywords |
| `mmcp/infrastructure/environment/config.py` | Modify | Add feature flags: `auto_invoke_cache`, `multi_stack_detection`, `cross_session_state`, `governance_dashboard`, `telemetry.integration.auto_invoke` |

## Interfaces / Contracts

```python
# auto_invoke_cache.py
class AutoInvokeCache:
    def get(self, key: str) -> Optional[Any]
    def set(self, key: str, value: Any, ttl_seconds: int) -> None
    def invalidate(self, key: str) -> None
    def clear(self) -> None
    def get_stats(self) -> dict  # hit rate, size, ttl_distribution

# auto_invoke_metrics.py
class AutoInvokeMetrics:
    def increment_invokes(self, host: str, agent: str, provider: str, model: str) -> None
    def record_tokens_saved(self, tokens: int) -> None
    def record_latency(self, latency_ms: float) -> None
    def get_summary(self) -> dict

# session_persistence.py
class SessionPersistence:
    def save_state(self, session_id: str, state: dict) -> None  # atomic
    def load_state(self, session_id: str) -> Optional[dict]
    def journal_replay(self) -> None
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Cache TTL/LRU, metrics counters, SHA-256 key stability | `pytest tests/` |
| Unit | Multi-stack detection env-var parsing | Mock env vars, verify detection |
| Integration | Persistence journal replay after simulated crash | Write state, crash-simulate, verify replay |
| Integration | Metrics emit to SQLite and query back | Insert fixture event, query via SessionStore |
| E2E | Dashboard render with live data | Mock SessionStore, assert panel output |

## Migration / Rollout

No migration required — all new components are additive. Feature flags default to safe behavior (`enabled: false`) so existing behavior is preserved until each flag is explicitly enabled.

## Open Questions

- [ ] Should `governance-dashboard` be a standalone CLI command or integrated into existing `context-life` TUI?
- [ ] Confirm skill path for `context-life-governance` — it's referenced in openspec but does not exist in `skills/` directory yet.
- [ ] Define exact TTL default value (spec says configurable, no suggested default).
