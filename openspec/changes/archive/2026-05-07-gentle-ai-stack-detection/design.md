# Design: gentle-ai-stack-detection

## Technical Approach

Extend `orchestrator_detector.py` with a new `OrchestratorFeatures` dataclass, add config-driven manual override, and implement a session-scoped tool call pattern tracker that infers orchestrator identity from observed MCP tool calls. The detection flow checks config first, then falls back to env vars → workspace artifacts → tool patterns.

## Architecture Decisions

### Decision: Session-scoped tool pattern tracker over global state

**Choice**: Tracker lives in `_ToolPatternTracker` instance stored on `AppContainer`, reset per session.
**Alternatives considered**: Module-level global (persists across sessions, hard to test), passing tracker as parameter (breaks existing call signatures).
**Rationale**: AppContainer already manages per-session singletons (`_rag_engine`, `_cache_loop`). Adding a tracker there keeps lifecycle managed and testable.

### Decision: Sliding window of 50 calls for pattern detection

**Choice**: `deque(maxlen=50)` per tracker instance.
**Alternatives considered**: Fixed window of 10 (too few for pattern emergence), unbounded (memory leak risk).
**Rationale**: 50 captures meaningful patterns without excessive memory. 3+ `intercept_user_request` calls within 50 is a strong gentle-ai signal.

### Decision: Config-driven mode check happens before any detection layers

**Choice**: `get_orchestrator_info()` reads `config.orchestrator_mode` first; if not `"auto"`, it forces detection and sets `manual_override=True`.
**Alternatives considered**: Config check after all auto layers fail (delays override, adds complexity).
**Rationale**: Manual override means "I know what I have, don't waste time detecting." Skipping detection layers is the whole point of override.

## Data Flow

```
get_orchestrator_info()
│
├─ Read config.orchestrator_mode
│    │
│    └─ if mode != "auto":
│         └─ _force_detection_from_mode(mode) → set manual_override=True
│              │
│              └─ Return early
│
└─ if mode == "auto":
     ├─ _check_env_vars()         [existing, returns early if hit]
     ├─ _check_workspace_artifacts() [existing, returns early if hit]
     └─ _check_tool_pattern(tracker)  [NEW - queries tracker]
          │
          └─ if orchestrator found → track detected tools in features
               else → set guidance="No orchestrator detected..."

_return OrchestratorInfo(features=OrchestratorFeatures(...))
```

Tool pattern tracker:
```
instrument_tool_call("intercept_user_request")
  → tracker.record("intercept_user_request")
  → tracker.signals["intercept_user_request"] = count
  → if count >= 3 and not detected: return gentle-ai via tool-pattern:intercept_user_request
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `mmcp/infrastructure/environment/orchestrator_detector.py` | Modify | Add `OrchestratorFeatures`, update `OrchestratorInfo`, add `_check_tool_pattern()`, `_force_detection_from_mode()`, tool pattern tracker class |
| `mmcp/infrastructure/environment/config.py` | Modify | Add `OrchestratorFeaturesConfig` dataclass, `orchestrator_mode` and `orchestrator_features` fields to `CLConfig`, load from TOML `[orchestrator]` section |
| `mmcp/presentation/mcp/server.py` | Modify | Update `orchestrator_resource()` to include `mode`, `guidance`, and expanded features dict |
| `mmcp/presentation/cli/diagnostics.py` | Modify | Add orchestrator section to `do_doctor()` showing mode, detected name, features with ✅/❌ |

## Interfaces / Contracts

### New Dataclass: `OrchestratorFeatures`

```python
@dataclass
class OrchestratorFeatures:
    has_engram: bool = False
    has_sdd_agents: bool = False
    has_skills: bool = False
    has_agent_teams: bool = False
    detected_tools: list[str] = field(default_factory=list)
```

### Modified: `OrchestratorInfo`

```python
@dataclass
class OrchestratorInfo:
    is_detected: bool = False
    orchestrator_name: str = "none"
    detection_method: str = "none"
    features: OrchestratorFeatures = field(default_factory=OrchestratorFeatures)
    advisor_mode: bool = False
    manual_override: bool = False  # NEW

    def to_dict(self) -> dict:
        return {
            "is_detected": self.is_detected,
            "orchestrator_name": self.orchestrator_name,
            "detection_method": self.detection_method,
            "features": dataclasses.asdict(self.features),  # expanded dict
            "advisor_mode": self.advisor_mode,
            "manual_override": self.manual_override,
        }
```

### New Config Dataclass: `OrchestratorFeaturesConfig`

```python
@dataclass
class OrchestratorFeaturesConfig:
    engram: bool = False
    sdd: bool = False
    skills: bool = False
    agents: bool = False

# In CLConfig:
orchestrator_mode: str = "auto"  # auto | gentle-ai | opencode | engram | none
orchestrator_features: OrchestratorFeaturesConfig = field(default_factory=OrchestratorFeaturesConfig)
```

### Tool Pattern Signals

| Signal | Pattern | Inference |
|--------|---------|-----------|
| `intercept_user_request` called 3+ times | sliding window | gentle-ai |
| `preflight_request` as first call | first-call check | opencode |
| `get_orchestration_advice` called frequently | count / total_calls ratio > 0.3 | active orchestrator |
| `mem_save`, `mem_search` detected | tools list | engram active |

### MCP Resource `status://orchestrator` response

```json
{
  "mode": "auto",
  "detected_orchestrator": "gentle-ai",
  "features": {
    "has_engram": true,
    "has_sdd_agents": true,
    "has_skills": true,
    "has_agent_teams": false,
    "detected_tools": ["mem_save", "sdd-propose"]
  },
  "detection_method": "tool-pattern:intercept_user_request",
  "manual_override": false,
  "guidance": null
}
```

When auto-detection finds nothing:
```json
{
  "mode": "auto",
  "detected_orchestrator": "none",
  "features": { "has_engram": false, ... },
  "detection_method": "none",
  "manual_override": false,
  "guidance": "No orchestrator detected. Configure manually in config.toml: [orchestrator] mode = \"gentle-ai\""
}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `OrchestratorFeatures`, `OrchestratorInfo.to_dict()`, mode-forced detection | pytest with tempfile config |
| Unit | `_check_tool_pattern()` with mock tracker | patch tracker, assert signal → name mapping |
| Unit | Config TOML loading `[orchestrator]` section | pytest with written config |
| Integration | `orchestrator_resource()` returns full expanded dict | TestMCP client hits resource |
| Integration | `mmcp doctor` shows orchestrator features | click CLI runner, assert output contains ✅/❌ |

## Migration / Rollout

No migration required. New fields default safely — existing callers using `orchestrator.to_dict()` get the new `features` as an expanded dict (thanks to `dataclasses.asdict()`) and `manual_override` defaults to `False`, preserving backward compatibility for callers that don't read it.

## Open Questions

- [ ] Should `_ToolPatternTracker` be reset when `reset_runtime_state()` is called? Currently it lives on `AppContainer`, not the runtime module — confirm lifecycle is acceptable.
- [ ] The spec says `detection_method` should be `"tool-pattern:intercept_user_request"` but we currently only set it as a string on `OrchestratorInfo`. Verify this format is acceptable for the MCP resource consumers.