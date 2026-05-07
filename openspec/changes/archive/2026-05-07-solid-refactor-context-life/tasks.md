# Tasks: solid-refactor-context-life

## Review Workload Forecast

| Field                   | Value                                            |
| ----------------------- | ------------------------------------------------ |
| Estimated changed lines | ~1800-2200                                       |
| 400-line budget risk    | High                                             |
| Chained PRs recommended | Yes                                              |
| Suggested split         | PR 1 (Phase 1) → PR 2 (Phase 2) → PR 3 (Phase 3) |
| Delivery strategy       | ask-on-risk                                      |
| Chain strategy          | stacked-to-main                                  |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal                                              | Likely PR | Notes                                                      |
| ---- | ------------------------------------------------- | --------- | ---------------------------------------------------------- |
| 1    | Phase 1: Token + Trim ports/adapters/strategies   | PR 1      | 11 tasks; backward compat via existing TokenCounterAdapter |
| 2    | Phase 2: SessionStore split + TelemetryService DI | PR 2      | 12 tasks; facade for backward compat                       |
| 3    | Phase 3: CLI split into ui/commands/telemetry_fmt | PR 3      | 9 tasks; thin cli.py re-imports                            |

---

## Phase 1: Token + Trim (Ports, Adapters, Strategy Pattern)

- [x] 1.1 Verify `mmcp/application/ports/token_counter.py` — add `clear_cache()` method to `TokenCounterPort` protocol (missing from current interface)
      **Verify**: `pytest tests/test_tokens_slice.py -v`
      **Dep**: None

- [x] 1.2 Create `mmcp/infrastructure/tokens/openai_token_counter.py` — implement `OpenAITokenCountingAdapter` wrapping existing `count_tokens`, `count_messages_tokens`, `get_cache_info`, `clear_cache` from `token_counter.py`
      **Verify**: `pytest tests/test_token_cache.py -v`
      **Dep**: 1.1

- [x] 1.3 Create `mmcp/application/ports/message_normalizer.py` — define `MessageNormalizerPort` protocol with `normalize(messages: list[dict]) -> list[dict]`
      **Verify**: `ruff check mmcp/application/ports/`
      **Dep**: None

- [x] 1.4 Create `mmcp/infrastructure/context/json_message_normalizer.py` — implement `JsonMessageNormalizerAdapter` (strips `_mmcp_cache_control` from messages, normalizes structure)
      **Verify**: `pytest tests/test_cache_manager.py -v`
      **Dep**: 1.3

- [x] 1.5 Update `mmcp/infrastructure/persistence/cache_manager.py` — inject `MessageNormalizerPort` via constructor; remove inline JSON normalization logic
      **Verify**: `pytest tests/test_cache_manager.py tests/test_cache_persistence.py -v`
      **Dep**: 1.4

- [x] 1.6 Create `mmcp/application/ports/trim_strategy.py` — define `TrimStrategyPort` protocol with `trim(messages, max_tokens, encoding) -> TrimResult`; add `TrimStrategy` enum to same file
      **Verify**: `ruff check mmcp/application/ports/`
      **Dep**: None

- [x] 1.7 Create `mmcp/infrastructure/context/trim_strategies.py` — implement `TailTrimStrategy`, `HeadTrimStrategy`, `SmartTrimStrategy` adapters (move logic from `trim_history.py`); keep `_extract_text_fragments` helper in trim_history.py (not a business rule)
      **Verify**: `pytest tests/test_trim_history.py -v`
      **Dep**: 1.6

- [x] 1.8 Create `mmcp/infrastructure/context/trim_orchestrator.py` — implement `TrimOrchestrator` that selects and delegates to appropriate strategy; injects token counter via constructor
      **Verify**: `pytest tests/test_trim_history.py tests/test_context_health.py -v`
      **Dep**: 1.7

- [x] 1.9 Update `mmcp/infrastructure/context/trim_history.py` — `trim_messages()` becomes thin wrapper that delegates to `TrimOrchestrator`; keep `TrimResult`, `TrimStrategy`, `ContextHealthReport`, `analyze_context_health()` unchanged
      **Verify**: `pytest tests/test_trim_history.py tests/test_context_health.py -v`
      **Dep**: 1.8

- [x] 1.10 Update `mmcp/application/features/tokens/adapters.py` — move `TokenCounterAdapter` from `application/features/` to `infrastructure/tokens/` (adapters belong in infrastructure layer per clean architecture); re-export from old location for backward compat
      **Verify**: `pytest tests/test_tokens_slice.py tests/test_token_cache.py -v`
      **Dep**: 1.2

- [x] 1.11 Run full Phase 1 verification
      **Verify**: `pytest tests/test_tokens_slice.py tests/test_token_cache.py tests/test_trim_history.py tests/test_context_health.py tests/test_cache_manager.py tests/test_cache_persistence.py -v`
      **Dep**: 1.1–1.10

---

## Phase 2: SessionStore Split + TelemetryService DI

- [ ] 2.1 Create `mmcp/application/ports/session_store_connection.py` — define `SessionStoreConnectionPort` protocol with `_init_db()`, lifecycle methods
      **Verify**: `ruff check mmcp/application/ports/`
      **Dep**: None

- [ ] 2.2 Create `mmcp/application/ports/session_store_migrations.py` — define `SessionStoreMigrationsPort` protocol with DDL methods for `prefix_cache_entries` and `usage_events` tables
      **Verify**: `ruff check mmcp/application/ports/`
      **Dep**: None

- [ ] 2.3 Create `mmcp/application/ports/session_store_queries.py` — define `SessionStoreQueriesPort` protocol with `lookup_prefix()`, `record_prefix_hit()`, `store_prefix()`, `evict_old_prefixes()`, `record_usage()`, `_aggregate_usage_since()`, `get_weekly_usage()`, `get_recent_stats()`, `get_all_time_stats()`
      **Verify**: `ruff check mmcp/application/ports/`
      **Dep**: None

- [ ] 2.4 Create `mmcp/application/ports/session_store_row_mapper.py` — define `SessionStoreRowMapperPort` protocol with row-to-domain mapping for `UsageEvent`
      **Verify**: `ruff check mmcp/application/ports/`
      **Dep**: None

- [ ] 2.5 Create `mmcp/infrastructure/persistence/session_store_connection.py` — implement `SessionStoreConnectionAdapter` wrapping sqlite3 connection lifecycle
      **Verify**: `pytest tests/test_cache_persistence.py -v`
      **Dep**: 2.1

- [ ] 2.6 Create `mmcp/infrastructure/persistence/session_store_migrations.py` — implement `SessionStoreMigrationsAdapter` with DDL for both tables and indexes
      **Verify**: `pytest tests/test_cache_persistence.py -v`
      **Dep**: 2.2

- [ ] 2.7 Create `mmcp/infrastructure/persistence/session_store_queries.py` — implement `SessionStoreQueriesAdapter` with all query methods
      **Verify**: `pytest tests/test_cache_persistence.py tests/test_telemetry_slice.py -v`
      **Dep**: 2.3

- [ ] 2.8 Create `mmcp/infrastructure/persistence/session_store_row_mapper.py` — implement `SessionStoreRowMapperAdapter` mapping SQLite rows to `UsageEvent`
      **Verify**: `pytest tests/test_telemetry_slice.py -v`
      **Dep**: 2.4

- [ ] 2.9 Create `mmcp/infrastructure/persistence/session_store_facade.py` — wire all 4 adapters together; re-export `SessionStore`, `UsageEvent`, `PrefixCacheStorePort` for backward compat
      **Verify**: `pytest tests/test_cache_persistence.py tests/test_telemetry_slice.py tests/test_app_container.py -v`
      **Dep**: 2.5–2.8

- [ ] 2.10 Update `mmcp/infrastructure/persistence/session_store.py` — make it a thin facade re-exporting from `session_store_facade.py`
      **Verify**: `pytest tests/test_cache_persistence.py tests/test_telemetry_slice.py tests/test_app_container.py -v`
      **Dep**: 2.9

- [ ] 2.11 Refactor `mmcp/infrastructure/telemetry/telemetry_service.py` — `TelemetryService` accepts `TelemetryStorePort` via constructor instead of lazy global `_get_telemetry_store()`; remove global state
      **Verify**: `pytest tests/test_telemetry_service.py -v`
      **Dep**: 2.9

- [ ] 2.12 Update `mmcp/presentation/app_container.py` — wire `TelemetryService` with `SessionStoreQueriesAdapter` via constructor (no longer creates SessionStore internally)
      **Verify**: `pytest tests/test_app_container.py tests/test_telemetry_service.py -v`
      **Dep**: 2.11

- [ ] 2.13 Run full Phase 2 verification
      **Verify**: `pytest tests/test_cache_persistence.py tests/test_telemetry_slice.py tests/test_telemetry_service.py tests/test_app_container.py -v`
      **Dep**: 2.1–2.12

---

## Phase 3: CLI Split into Presentation/Application/Domain Layers

- [ ] 3.1 Analyze `install_context_life` — determine it is pure logic (no visual/UI parts) → stays in `infrastructure/installation/`
      **Verify**: Code review — no TUI, no Rich, no ANSI
      **Dep**: None

- [ ] 3.2 Analyze `_extract_text_fragments` — determine it is a helper (not a business rule) → stays in `infrastructure/context/`
      **Verify**: Code review — internal helper only
      **Dep**: None

- [ ] 3.3 Create `mmcp/presentation/cli/ui/__init__.py`
      **Verify**: `ruff check mmcp/presentation/cli/`
      **Dep**: None

- [ ] 3.4 Extract `widgets.py` from `cli.py` — move `MenuItem`, `MenuScreen`, `DetailPage`, `MenuActionResult`, and all widget helper functions (`_compact_panel`, `_compact_list_panel`, etc.)
      **Verify**: `python -c "from mmcp.presentation.cli.widgets import MenuItem, MenuScreen; print('OK')"`
      **Dep**: 3.3

- [ ] 3.5 Extract `ansi.py` from `cli.py` — move ANSI escape sequence helpers (`_ensure_utf8_output`, `_render_renderable_to_lines`, `_markup_text`, etc.)
      **Verify**: `python -c "from mmcp.presentation.cli.ansi import _ensure_utf8_output; print('OK')"`
      **Dep**: 3.3

- [ ] 3.6 Extract `render.py` from `cli.py` — move layout functions (`_build_internal_divider`, `_build_linear_detail_sections`, `_call_detail_builder`, `_stack_renderables`, `_resolve_detail_layout`, `_build_menu_panel`, `_build_tui_header`)
      **Verify**: `python -c "from mmcp.presentation.cli.render import _build_menu_panel; print('OK')"`
      **Dep**: 3.3

- [ ] 3.7 Extract `input.py` from `cli.py` — move `_read_tui_key` cross-platform input reader
      **Verify**: `python -c "from mmcp.presentation.cli.input import _read_tui_key; print('OK')"`
      **Dep**: 3.3

- [ ] 3.8 Extract `telemetry_fmt.py` from `cli.py` — move domain formatting (`_build_rag_warmup_table`, `_build_rag_warmup_summary_panel`, `_warmup_status_lines`, `_warmup_modes_lines`, `_build_warmup_status_detail_page`, `_build_warmup_modes_detail_page`, `_render_rag_warmup_interactive_selector`)
      **Verify**: `python -c "from mmcp.presentation.cli.telemetry_fmt import _build_rag_warmup_table; print('OK')"`
      **Dep**: 3.3

- [ ] 3.9 Extract `commands.py` from `cli.py` — move command handlers (`do_upgrade`, `do_rag_warmup_command`, `prewarm_rag_now_cli`, `run_rag_warmup_interactive`, `show_rag_warmup_info`, `show_info`, `set_rag_warmup_mode`, `_install_context_life_and_return`, `_build_*_menu` functions, `_build_*_content`, `_build_*_pages`)
      **Verify**: `python -c "from mmcp.presentation.cli.commands import do_upgrade; print('OK')"`
      **Dep**: 3.3

- [ ] 3.10 Rewrite `mmcp/presentation/cli/cli.py` — thin entrypoint that imports and re-exports from extracted modules; keep `_show_stateful_menu`, `_show_in_scrollable_screen` as orchestration layer
      **Verify**: `python -c "from mmcp.presentation.cli.cli import show_info; print('OK')"`
      **Dep**: 3.4–3.9

- [ ] 3.11 Run full Phase 3 verification
      **Verify**: `pytest tests/test_cli_unicode.py tests/test_rag_warmup_cli.py tests/test_upgrade_cli.py tests/test_cli_command_service.py -v`
      **Dep**: 3.1–3.10

---

## Notes

- **Parallelism within phases**: Tasks 1.1–1.5 can run in parallel (no shared state changes until 1.6+). Task 1.10 depends on 1.2. All other Phase 1 tasks are sequential.
- **Phase 2 parallelism**: Tasks 2.1–2.4 can run in parallel (only define ports). Tasks 2.5–2.8 can run in parallel after their ports are done. Tasks 2.9–2.12 are sequential.
- **Phase 3 parallelism**: Tasks 3.3–3.9 are independent (each extracts a different module). Task 3.10 is sequential (needs all modules extracted).
- **Backward compat**: Phase 1 re-exports from old location; Phase 2 facade re-exports `SessionStore`, `UsageEvent`; Phase 3 cli.py re-exports for internal callers.
- **Strict TDD**: Run tests after each task split, not after a group, per `strict_tdd: true`.
