# Proposal: solid-refactor-context-life

## Intent

Address SOLID violations identified in exploration while preserving all existing functionality. The codebase has grown a God File problem and violation of Single Responsibility, Dependency Inversion, and Open/Closed principles. This refactor restores clean architecture seams without changing behavior.

## Scope

### In Scope
- Split `session_store.py` into connection management, migration management, domain queries, and row mappers
- Split `cli.py` into presentation layer (UI/rendering), application layer (commands), and domain adapters
- Inject `TelemetryStore` as dependency instead of internal creation in `telemetry_service.py`
- Isolate vendor-specific token heuristics in `token_counter.py` behind a port interface
- Extract trim strategies in `trim_history.py` behind a Strategy interface
- Decouple `cache_manager.py` from JSON schema via message normalization port

### Out of Scope
- New features or behavior changes
- Database schema changes
- Test suite restructuring (keep green)

## Capabilities

> This is a pure refactor — no spec-level behavior changes.

### New Capabilities
- None

### Modified Capabilities
- None

## Approach

1. **session_store.py → 4 classes**: Extract `ConnectionManager` (lifecycle), `MigrationManager` (DDL), `SessionRepository` (domain queries), `SessionRowMapper` (transformation). Use existing interface as seam.

2. **cli.py → 3 layers**: Extract `CLIPresenter` (rendering/ANSI), `CLICommandHandler` ( orchestration), `InputAdapter` (OS-specific). Thin entrypoint remains.

3. **telemetry_service.py → dependency injection**: Replace `_get_telemetry_store()` lazy global and `SessionStore` internal creation. Accept `TelemetryStore` via constructor/parameter.

4. **token_counter.py → port interface**: Define `TokenCounter` protocol. Keep OpenAI-specific heuristics behind `OpenAITokenCounter` implementation. Inject appropriate counter.

5. **trim_history.py → strategy pattern**: Extract `_extract_text_fragments` conditional ladder into `TrimStrategy` implementations (by message role). Selector class picks strategy.

6. **cache_manager.py → normalization port**: Define `MessageNormalizer` protocol. CacheLoop depends on normalized interface, not raw JSON schema.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/mcp_server/session_store.py` | Modified | Split into 4 focused components |
| `src/mcp_server/cli.py` | Modified | Split into presentation/application/domain layers |
| `src/mcp_server/telemetry_service.py` | Modified | DI instead of internal creation |
| `src/mcp_server/token_counter.py` | Modified | Port/impl for token counting |
| `src/mcp_server/trim_history.py` | Modified | Strategy pattern for trim |
| `src/mcp_server/cache_manager.py` | Modified | Normalizer port for cache schema |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Behavior drift during refactor | Medium | strict_tdd: run tests after each split; verify before moving to next |
| Circular dependency from split | Low | Map deps before cut; use solid-review skill |
| Interface explosion | Low | Keep ports minimal; extract only where violation exists |

## Rollback Plan

Git branch per phase. If a split introduces regression:
1. Revert specific file to pre-split version
2. Run tests — must pass on revert
3. Re-architect the split before continuing
No destructive changes — all original code moved, not deleted.

## Dependencies

- `solid-review` skill for each split decision
- `behavior-selection-refactor` for strategy pattern extraction

## Success Criteria

- [ ] All existing tests pass after each split
- [ ] No circular imports introduced
- [ ] Each class/module has single, documented responsibility
- [ ] Dependencies flow inward (domain has no infra imports)
- [ ] `ruff check` passes with no new violations