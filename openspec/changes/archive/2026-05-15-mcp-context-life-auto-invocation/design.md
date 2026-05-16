# Design: mcp-context-life-auto-invocation

## Technical Approach

Auto-invoke context-life at prompt boundaries using an MCP tool (`autoinvoke_context`) triggered by the host agent. Stack type (solo-agent vs orchestrator) is detected at session start via env vars + workspace artifacts. Governance differs per stack:

- **solo-agent** (Windsurf, Codex, Claude Code): Skill `context-life.md` instructs LLM to call `autoinvoke_context` as first token
- **orchestrator with delegate()** (gentle-ai, custom): Orchestrator delegates to `context-life-advisor` sub-agent before SDD phases

Session ID is derived server-side (not passed by LLM). Strict TDD with RED-GREEN-REFACTOR per task.

## Architecture Decisions

| Decision | Options | Chosen | Rationale |
|---|---|---|---|
| Stack detection logic | env vars + artifacts, explicit ELSE | IF `GENTLE_AI_ACTIVE=1` AND `.gga` → gentle-ai, ELSE → solo-agent | Explicit else prevents partial-signal limbo |
| Session ID derivation | env var / file with TTL / hash | File `.context-session.id` with 12h TTL, fallback to hash | Survives server restarts |
| Advisor stack-agnostic | gentle-ai only / any with delegate() | Any orchestrator with `delegate()` support | User can use custom stack |
| Solo-agent governance | skill-based / tool-based | Skill `context-life.md` (prompt instruction) | Solo-agents can't delegate |

## Data Flow

### Solo-Agent Wake Flow (Zero-Step)

```
Solo-Agent Start
  └─> stack_detector.detect() → "solo-agent"
  └─> skill injects: "call autoinvoke_context as FIRST token"
  └─> LLM calls autoinvoke_context(stack_type="solo-agent")
  └─> MCP server derives session_id (from env/file/hash)
  └─> MCP server loads prior state from ~/.config/context-life/sessions/{id}/state.json
  └─> MCP server returns ContextPack with merged state
  └─> LLM proceeds with enriched context
  └─> LLM calls sleep_context() at task end
  └─> MCP server persists state to state.json
```

### Orchestrator-Mediated Flow (Zero-Step Routing)

```
Orchestrator receives prompt
  └─> stack_detector.detect() → "gentle-ai" or custom
  └─> orchestrator.delegate(agent="context-life-advisor", prompt=raw)
  └─> advisor calls autoinvoke_context(stack_type)
  └─> MCP server handles extraction/indexing internally (single call)
  └─> advisor returns ContextPack to orchestrator
  └─> orchestrator proceeds to SDD phase (sdd-propose, etc.)
```

### Session ID Derivation (Server-Side)

```
autoinvoke_context called
  └─> IF ENGRAM_SESSION_ID env var → use directly
  └─> ELSE IF .context-session.id exists AND < 12h old → read from file
  └─> ELSE → compute hash(cwd + timestamp), save to .context-session.id, use it
  └─> Return active_session_id in ContextPack for LLM awareness
```

## File Changes

| File | Action | Description |
|---|---|---|
| `mmcp/orchestration/stack_detector.py` | Create | `detect()` returns solo-agent OR orchestrator type |
| `mmcp/presentation/mcp/tools/auto_invoke.py` | Create | `@mcp.tool() autoinvoke_context(stack_type)` — session_id server-side |
| `mmcp/domain/session_state.py` | Create | SessionState enum, SessionStateMachine with transition() |
| `mmcp/infrastructure/session_id_resolver.py` | Create | Derives session_id from env/file/hash, manages .context-session.id |
| `mmcp/infrastructure/persistence/context_state_store.py` | Create | Unified interface; FS adapter for solo, Engram adapter for multi |
| `mmcp/infrastructure/persistence/file_system_adapter.py` | Create | Persists to `~/.config/context-life/sessions/{id}/state.json` |
| `skills/context-life/SKILL.md` | Create | Zero-Step wake/sleep instructions for solo-agent |
| `opencode.json` agents array | Modify | Append `context-life-advisor` definition via installer |
| `context_life_installer.py` | Modify | Safe list merge (append, don't overwrite agents array) |

## Interfaces / Contracts

### autoinvoke_context Tool (MCP)

```python
@mcp.tool()
def autoinvoke_context(stack_type: str) -> dict:
    """
    Session ID derived server-side (not a parameter).

    Returns JSON: {
        "context_items": [...],
        "session_state": {...},
        "recommendations": [...],
        "active_session_id": str,  # server-computed, for LLM awareness
        "level": "REQUIRED" | "LIGHT" | "CRITICAL"
    }
    """
```

### sleep_context Tool (MCP)

```python
@mcp.tool()
def sleep_context() -> dict:
    """
    Persists current session learnings to server.
    Called by LLM at task end (solo-agent) or by orchestrator (multi-agent).

    Returns: {"status": "persisted", "session_id": str}
    """
```

### SessionStateStore Interface

```python
class ContextStateStore(Protocol):
    def load(self, session_id: str) -> Optional[SessionState]: ...
    def persist(self, session_id: str, state: SessionState) -> None: ...
    def delete(self, session_id: str) -> None: ...
```

### SessionState Machine

```python
class SessionState(Enum):
    IDLE = auto()
    WAKING = auto()    # solo-agent: loading prior state
    ACTIVE = auto()    # solo-agent: executing prompt
    SLEEPING = auto()  # solo-agent: persisting state
    HANDS_OFF = auto() # orchestrator: delegated to advisor

class SessionStateMachine:
    def transition(self, to: SessionState) -> SessionState: ...
    def get_current_state(self) -> SessionState: ...
```

### StackDetector

```python
class StackDetector:
    def detect() -> StackType:
        """
        Returns solo-agent OR orchestrator.
        IF GENTLE_AI_ACTIVE=1 AND .gga exists → orchestrator (gentle-ai or custom)
        ELSE → solo-agent
        """
```

### context-life-advisor Sub-Agent

```python
# Registered in opencode.json agents array
{
    "name": "context-life-advisor",
    "description": "Optimizes context before orchestrator starts SDD phases",
    "system_prompt": "You are the context-life-advisor. Call autoinvoke_context(stack_type) and return ContextPack as ground truth.",
    "tools": ["autoinvoke_context"],
    "model": "qwen3"
}
```

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | StackDetector logic | Mock env vars + filesystem; test detection paths |
| Unit | Session ID resolver | Mock file system; test env/file/hash derivation and TTL |
| Unit | autoinvoke_context tool contract | Patch StackDetector; verify correct branch per stack_type |
| Unit | State machine transitions | Valid/invalid transitions |
| Integration | Solo-agent full cycle (wake→prompt→sleep) | tmp_path fixture for state file |
| Integration | Orchestrator delegate flow | Mock delegate(); verify advisor called with correct prompt |
| Integration | DISABLE_AUTOINVOKE=1 bypass | Verify no side effects when flag set |

## Migration / Rollout

No migration required. New files only. `DISABLE_AUTOINVOKE=1` env var disables all behavior silently — backward compatible with existing deployments.

## Open Questions

- [x] Should `autoinvoke_context` be auto-triggered or explicit? → Zero-Step enforced via skill/orchestrator routing
- [x] Does `context-life-advisor` already exist? → No, needs creation via installer
- [x] Is session_id derived server-side? → Yes, removed from tool signature
- [x] Is advisor stack-agnostic? → Yes, works with any orchestrator with delegate()
- [ ] What model for advisor? → qwen3 (fast, JSON tool calling)
- [ ] DISABLE_AUTOINVOKE behavior for orchestrator? → Returns bypass message, orchestrator proceeds normally