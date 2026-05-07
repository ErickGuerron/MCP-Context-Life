# Tasks: gentle-ai-stack-detection

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~380–460 (detection logic + config + resource + diagnostics + 4 test modules) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |

Decision needed before apply: Yes
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Phase 1+2: Config + Dataclasses + Detection Logic | PR 1 | Includes tracker instrumentation; tests included |

## Phase 1: Config + Dataclasses

- [x] 1.1 Add `OrchestratorFeatures` dataclass to `orchestrator_detector.py`
      **Verify**: `pytest tests/test_orchestrator_detector.py -k "test_orchestrator_features"`
      **Dep**: —
- [x] 1.2 Update `OrchestratorInfo` — add `manual_override: bool`, change `features` to `OrchestratorFeatures`, add `to_dict()` method
      **Verify**: `pytest tests/test_orchestrator_detector.py -k "test_to_dict"`
      **Dep**: 1.1
- [x] 1.3 Add `OrchestratorFeaturesConfig` dataclass to `config.py`
      **Verify**: `pytest tests/test_config.py -k "test_orchestrator_features_config"`
      **Dep**: —
- [x] 1.4 Add `orchestrator_mode` and `orchestrator_features` fields to `CLConfig`, load from TOML `[orchestrator]` section in `load_config()`
      **Verify**: `pytest tests/test_config.py -k "test_orchestrator_toml_loading"`
      **Dep**: 1.3

## Phase 2: Detection Logic

- [x] 2.1 Implement `_force_detection_from_mode(mode)` in `orchestrator_detector.py`
      **Verify**: `pytest tests/test_orchestrator_detector.py -k "test_force_detection_from_mode"`
      **Dep**: 1.2, 1.4
- [x] 2.2 Implement `_ToolPatternTracker` class with `record()`, `signals` dict, sliding window (`deque(maxlen=50)`)
      **Verify**: `pytest tests/test_orchestrator_detector.py -k "test_tool_pattern_tracker"`
      **Dep**: 1.1
- [x] 2.3 Implement `_check_tool_pattern(tracker)` method — detect gentle-ai (3+ `intercept_user_request`), opencode (`preflight_request` first), active orchestrator (high `get_orchestration_advice` ratio)
      **Verify**: `pytest tests/test_orchestrator_detector.py -k "test_check_tool_pattern"`
      **Dep**: 2.2
- [x] 2.4 Update `get_orchestrator_info()` to check `config.orchestrator_mode` first, call `_force_detection_from_mode()` if not auto, else run env → artifacts → tool-pattern layers
      **Verify**: `pytest tests/test_orchestrator_detector.py -k "test_get_orchestrator_info_integration"`
      **Dep**: 2.1, 2.3
- [x] 2.5 Add `record_tool_call(tool_name)` function in `server.py` or `app_container.py` to feed the tracker; store tracker on `AppContainer`
      **Verify**: `pytest tests/test_orchestrator_detector.py -k "test_record_tool_call"`
      **Dep**: 2.2

## Phase 3: MCP Resource + Diagnostics

- [x] 3.1 Update `status://orchestrator` resource in `server.py` to return full expanded schema: `mode`, `guidance` (when no detection), `detected_orchestrator`, features dict, `manual_override`
      **Verify**: `pytest tests/ -k "test_orchestrator_resource" -v`
      **Dep**: 2.4, 1.2
- [x] 3.2 Update `mmcp doctor` in `diagnostics.py` to show orchestrator mode, detected name, features with ✅/❌ indicators
      **Verify**: `pytest tests/ -k "test_doctor_orchestrator" -v`
      **Dep**: 2.4, 1.2

## Phase 4: Testing

- [x] 4.1 Add unit tests for `OrchestratorFeatures`, `OrchestratorInfo.to_dict()` expanded fields, `manual_override`
      **Verify**: `pytest tests/test_orchestrator_detector.py -k "TestOrchestratorFeatures"`
      **Dep**: 1.1, 1.2
- [x] 4.2 Add unit tests for config TOML loading `[orchestrator]` section (mode=gentle-ai, mode=none, unknown mode defaults to auto, features section)
      **Verify**: `pytest tests/test_config.py -k "test_orchestrator_section"`
      **Dep**: 1.3, 1.4
- [x] 4.3 Add unit tests for `_force_detection_from_mode()` with mock config
      **Verify**: `pytest tests/test_orchestrator_detector.py -k "test_force_detection_from_mode"`
      **Dep**: 2.1
- [x] 4.4 Add unit tests for `_check_tool_pattern()` with mock tracker (gentle-ai signal after 3 intercepts, opencode preflight first, no detection)
      **Verify**: `pytest tests/test_orchestrator_detector.py -k "test_check_tool_pattern"`
      **Dep**: 2.3

## Notes

- **Parallelism within phases**: Tasks 1.1–1.5 can run in parallel (no shared state changes until 1.6+). Task 1.10 depends on 1.2. All other Phase 1 tasks are sequential.
- **Phase 2 parallelism**: Tasks 2.1–2.4 can run in parallel (only define ports). Tasks 2.5–2.8 can run in parallel after their ports are done. Tasks 2.9–2.12 are sequential.
- **Phase 3 parallelism**: Tasks 3.3–3.9 are independent (each extracts a different module). Task 3.10 is sequential (needs all modules extracted).
- **Backward compat**: Phase 1 re-exports from old location; Phase 2 facade re-exports `SessionStore`, `UsageEvent`; Phase 3 cli.py re-exports for internal callers.
- **Strict TDD**: Run tests after each task split, not after a group, per `strict_tdd: true`.