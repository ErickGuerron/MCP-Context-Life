# Tasks: mcp-context-life-auto-invocation

## Review Workload Forecast

| Field                   | Value                                                |
| ----------------------- | ---------------------------------------------------- |
| Estimated changed lines | ~700–900                                             |
| 400-line budget risk    | High                                                 |
| Chained PRs recommended | Yes                                                  |
| Suggested split         | PR 1 (Foundation) → PR 2 (Core) → PR 3 (Integration) |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal                                     | PR   | Notes                                                     |
| ---- | ---------------------------------------- | ---- | --------------------------------------------------------- |
| 1    | Stack Detection + Session ID Resolver    | PR 1 | Base infrastructure; tests included                       |
| 2    | Auto-Invoke + Sleep Tools                | PR 2 | Core MCP tools; depends on PR 1                           |
| 3    | Governance Skill + Advisor + Persistence | PR 3 | Skill, sub-agent, and filesystem adapter; depends on PR 2 |

## Phase 1: Stack Detection + Session ID Resolver

- [x] 1.1 Create `mmcp/orchestration/stack_detector.py` — `detect()` returns `solo-agent` if no signals, else `orchestrator`
  - Detection logic: ENGRAM_ACTIVE=1 OR ENGRAM_SESSION_ID set OR GENTLE_AI_ACTIVE=1 → orchestrator, ELSE → solo-agent
  - DISABLE_AUTOINVOKE=1 bypasses detection and returns SOLO_AGENT
  - Rationale: Engram signals indicate multi-agent/orchestrator context (pure solo-agent does not activate Engram MCP)
- [x] 1.2 Add unit tests for stack detection: Engram signals, GENTLE_AI_ACTIVE alone, DISABLE_AUTOINVOKE=1 bypass, .gga alone → solo-agent (8 tests passing)
- [x] 1.3 Create `mmcp/infrastructure/session_id_resolver.py` — `resolve()` derives session_id server-side
  - IF `ENGRAM_SESSION_ID` env var → use directly
  - ELSE IF `.context-session.id` exists AND < 12h old → read from file
  - ELSE → compute `hash(cwd + timestamp)`, persist to `.context-session.id`
- [x] 1.4 Add unit tests for session ID resolver: env var path, file read path, new hash path, TTL expiry
- [x] 1.5 Create `mmcp/domain/session_state.py` — `SessionState` enum (IDLE/WAKING/ACTIVE/SLEEPING/HANDS_OFF), `SessionStateMachine` class
- [x] 1.6 Add unit tests for state machine: valid transitions, invalid transition raises error

## Phase 2: Auto-Invoke + Sleep MCP Tools

- [x] 2.1 Create `mmcp/presentation/mcp/tools/auto_invoke.py`
  - `@mcp.tool() def autoinvoke_context(stack_type: str) -> dict`
  - Session ID derived internally via `SessionIdResolver.resolve()`
  - Returns ContextPack with `context_items`, `session_state`, `recommendations`, `active_session_id`, `level`
- [x] 2.2 Add unit tests: mock StackDetector + SessionIdResolver, verify correct branch per stack_type
- [x] 2.3 Implement branch logic:
  - solo-agent: calls `ContextOptimizer.run()`, loads prior state, returns ContextPack
  - orchestrator: delegates to `context-life-advisor` sub-agent via `delegate()`
- [x] 2.4 Add RED test for DISABLE_AUTOINVOKE=1 bypass, then GREEN implement env var check at top of tool
- [x] 2.5 Create `mmcp/presentation/mcp/tools/sleep_context.py`
  - `@mcp.tool() def sleep_context() -> dict`
  - Persists current session learnings to filesystem
  - Returns `{"status": "persisted", "session_id": str}`
- [x] 2.6 Add unit tests for sleep_context: persist cycle, DISABLE_AUTOINVOKE=1 bypass

## Phase 3: Governance Skill + Advisor Sub-Agent + Persistence

### 3.1: Solo-Agent Governance Skill

- [x] 3.1.1 Create `skills/context-life/SKILL.md`
  - Zero-Step wake: "ABSOLUTE FIRST token MUST be `autoinvoke_context(stack_type='solo-agent')`"
  - Sleep: "MUST call `sleep_context()` at task end"
  - Chat history treated as volatile
- [x] 3.1.2 Document DISABLE_AUTOINVOKE=1 fallback

### 3.2: context-life-advisor Sub-Agent

- [x] 3.2.1 Create `context_life_installer.py` logic to append agent to `opencode.json` agents array (safe merge: append, don't overwrite)
- [x] 3.2.2 Define agent in `opencode.json`:
  ```json
  {
    "name": "context-life-advisor",
    "description": "Optimizes context before orchestrator starts SDD phases",
    "system_prompt": "You are the context-life-advisor. Call autoinvoke_context(stack_type) and return ContextPack as ground truth. Do not write code.",
    "tools": ["autoinvoke_context"],
    "model": "qwen3"
  }
  ```
- [x] 3.2.3 Verify installer handles missing agents array gracefully

### 3.3: Persistence Layer

- [x] 3.3.1 Create `mmcp/infrastructure/persistence/context_state_store.py` — `ContextStateStore` protocol (load/persist/delete), factory returning FS or Engram adapter
- [x] 3.3.2 Create `mmcp/infrastructure/persistence/file_system_adapter.py` — persists to `~/.config/context-life/sessions/{id}/state.json`, handles missing directory
- [x] 3.3.3 Add unit tests: tmp_path fixture, read/write cycle, missing dir creation
- [x] 3.3.4 Add RED test for Engram adapter fallback (multi-agent), then GREEN implement

### 3.4: Phase Guardian (Optional for v1)

- [x] 3.4.1 Create `mmcp/orchestration/phase_guardian.py` — validates spec exists before apply; logs to Engram
- [x] 3.4.2 Add unit tests: mock Engram, verify error on missing spec

## Phase 4: Integration Tests

- [x] 4.1 Write integration test: solo-agent full cycle (wake→prompt→sleep) using tmp_path for state file
- [x] 4.2 Write integration test: orchestrator delegate flow with mocked delegate()
- [x] 4.3 Write integration test: DISABLE_AUTOINVOKE=1 disables all behavior silently
- [x] 4.4 Write integration test: session survives server restart (TTL check)

## Implementation Order

```
Phase 1 (Stack Detection + Session ID) →
Phase 2 (Auto-Invoke + Sleep Tools) →
Phase 3.3 (Persistence) →
Phase 3.1 (Skill) + Phase 3.2 (Advisor) + Phase 3.4 (Phase Guardian) [can run in parallel after Phase 2] →
Phase 4 (Integration Tests)
```

Phase 2 depends on Phase 1. Phases 3.1, 3.2, 3.4 can be developed in parallel once the tool contract exists. Phase 4 runs after everything is integrated.

## Dependencies

- StackDetector depends on `orchestrator_detector.py` (existing)
- SessionIdResolver manages `.context-session.id` file
- Auto-invoke tools depend on StackDetector + SessionIdResolver
- Advisor sub-agent requires `delegate()` in orchestrator
- Persistence can work standalone (used by both solo-agent and orchestrator modes)
