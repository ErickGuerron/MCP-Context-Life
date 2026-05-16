# Design: Context Optimization & HALT Governance Layer (Deliverable 4)

## Technical Approach

Implement a **pre-processor layer** that intercepts raw user prompts before they reach the orchestrator, classifies context quality (LIGHT/REQUIRED/CRITICAL), resolves missing context from project memory (Engram, sdd-init, skill-registry), detects contradictions, and outputs a compact **Context Pack** JSON consumed by gentle-orchestrator or SDD agents.

The layer is NOT a replacement for sdd-init, Engram, or gentle-orchestrator — it sits in front as a normalization step that produces compact, structured input.

## Architecture Decisions

### Decision: Three-tier state machine over binary complete/incomplete

**Choice**: LIGHT / REQUIRED / CRITICAL with deterministic confidence scoring
**Alternatives**: Binary (complete/incomplete), five-tier maturity model
**Rationale**: Three states map directly to action paths — inject compact summary, restructure prompt, or HALT. Confidence thresholds (0.80/0.55) are simple and predictable. Any contradiction forces CRITICAL regardless of score.

### Decision: Engram as primary context store, filesystem as fallback

**Choice**: Query Engram first via `mem_search`/`mem_get_observation`, then fall back to scanning `sdd-init/{project}`, `.atl/skill-registry.md`, `package.json`, `README.md`
**Alternatives**: Always scan filesystem, always query Engram
**Rationale**: Engram persists cross-session memory — conventions, detected stack, user preferences. Filesystem is the source of truth for current project state.，两者互补。

### Decision: ConflictDetector checks README vs package.json, memory vs code, git vs structure

**Choice**: Explicit contradiction checks between: (1) README vs package.json/pyproject.toml, (2) Engram memory vs current code policies, (3) git history vs current structure, (4) explicit prompt vs detected stack
**Alternatives**: Single contradiction check, no contradiction detection
**Rationale**: The CRITICAL state exists specifically to catch contradictions that would produce wrong solutions. Detection must be concrete: exact mismatches between documented intent and actual code.

### Decision: ContextBudgetManager maps to four tiers

| Budget | Tokens | When |
|--------|--------|------|
| `tiny` | ~200 | CRITICAL (HALT) or very short prompt |
| `small` | ~500 | LIGHT with stale/missing context |
| `medium` | ~1000 | REQUIRED or LIGHT with partial context |
| `full` | no limit | LIGHT with fresh complete context |

**Rationale**: Matches Gentle AI's sub-agent isolation model. Smaller context budgets force focused, independent work windows.

### Decision: HALT output is a structured JSON response, not an exception

**Choice**: Return `{"halt": true, "detected_goal": ..., "conflict": ..., "risk": ..., "required_decision": [...]}` from the ContextOptimizer
**Alternatives**: Raise custom exception, write to stderr
**Rationale**: MCP tools return JSON strings. A structured HALT response flows naturally through the existing `intercept_user_request` return path without protocol changes.

## Data Flow

```
Raw Prompt
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  PromptContextClassifier                                │
│  ├─ Analyze prompt completeness, ambiguity, signals     │
│  ├─ Compute confidence score (0.0-1.0)                   │
│  └─ Emit: LIGHT | REQUIRED | CRITICAL                   │
└─────────────────────────────────────────────────────────┘
    │
    ├─ LIGHT ────────────────────────────────────────────►│
    │                                                        │
    ▼                                                        ▼
┌────────────────────┐              ContextBudgetManager      │
│ProjectContextResolver│◄───────── determines budget          │
│ ├─ Engram (memory)  │                                  │
│ ├─ sdd-init/        │                                  │
│ ├─ skill-registry   │                                  │
│ ├─ package.json     │                                  │
│ ├─ README.md        │                                  │
│ └─ git diff/log     │                                  │
└────────────────────┘                                  │
    │                                                    │
    ▼                                                    ▼
┌────────────────────┐              ┌─────────────────────────┐
│ConflictDetector    │─────────────►│  HALTGate (if CRITICAL) │
│ ├─ README vs deps  │              │  Returns structured     │
│ ├─ memory vs code │              │  HALT JSON, stops flow  │
│ ├─ git vs struct  │              └─────────────────────────┘
│ └─ prompt vs stack│
└────────────────────┘
    │
    ▼
┌────────────────────┐
│ContextPackBuilder  │ ─────────────────────────────────► Context Pack JSON
│ ├─ goal           │
│ ├─ files          │
│ ├─ constraints    │
│ └─ output         │
└────────────────────┘
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `mmcp/application/features/context/classifiers.py` | Create | `PromptContextClassifier`, `ConflictDetector`, signal constants |
| `mmcp/application/features/context/resolver.py` | Create | `ProjectContextResolver`, `ContextBudgetManager` |
| `mmcp/application/features/context/pack_builder.py` | Create | `ContextPackBuilder`, `ContextPack` dataclass |
| `mmcp/application/features/context/context_optimizer.py` | Create | `ContextOptimizer` — main orchestrator composing all components |
| `mmcp/presentation/mcp/server.py` | Modify | `intercept_user_request` delegates to `ContextOptimizer`, returns packed JSON |

## Interfaces / Contracts

### ContextPack dataclass
```python
@dataclass
class ContextPack:
    goal: str
    state: Literal["LIGHT", "REQUIRED", "CRITICAL"]
    confidence: float
    context_budget: Literal["tiny", "small", "medium", "full"]
    project_context: dict          # stack, architecture, testing, package_manager
    files: dict                   # explicit[], inferred[]
    constraints: list[str]
    missing_context: list[str]
    next_action: str
    halt: Optional[HaltDetail] = None
```

### HaltDetail dataclass
```python
@dataclass
class HaltDetail:
    detected_goal: list[str]
    conflict: list[str]            # "Source A: ...", "Source B: ..."
    risk: str
    required_decision: list[str]
```

### PromptContextClassifier signals
```python
# LIGHT signals (confidence > 0.80)
LIGHT_SIGNALS = ["clear_goal", "explicit_files", "stack_mentioned", "constraint_listed"]

# REQUIRED signals (0.55 <= confidence <= 0.79)
REQUIRED_SIGNALS = ["vague_goal", "partial_files", "implicit_stack", "loose_constraints"]

# CRITICAL triggers (forced regardless of confidence)
CRITICAL_TRIGGERS = [
    "readme_stack_mismatch",     # README says X but package.json says Y
    "memory_policy_conflict",    # memory says "don't use X" but code uses it
    "destructive_operation",     # data deletion, auth migration, security changes
    "breaking_public_api",       # semver-major change implied
    "ambiguous_architecture",    # two active architectures possible
]
```

### Confidence scoring (deterministic)
```python
def compute_confidence(prompt: str, signals: list[str]) -> float:
    base = 0.5
    for signal in signals:
        if signal in LIGHT_SIGNALS:
            base += 0.15
        elif signal in REQUIRED_SIGNALS:
            base += 0.05
        # CRITICAL signals cap at 0.0 and force CRITICAL state
    return min(1.0, max(0.0, base))
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `PromptContextClassifier` signal detection | Mock prompts with known signals, assert correct state + confidence |
| Unit | `compute_confidence` determinism | Same input → same output across N calls |
| Unit | `ConflictDetector` for each contradiction type | Mock Engram responses + filesystem reads, assert detection |
| Unit | `ContextBudgetManager` tier mapping | Assert tiny/small/medium/full thresholds |
| Unit | `ContextPackBuilder` output shape | Assert all required fields present, types correct |
| Integration | Full flow: prompt → Context Pack | End-to-end with real (mocked) Engram + filesystem |
| HALT scenario | CRITICAL contradiction detected | Assert `halt=True`, `state="CRITICAL"`, structured conflict array |

## Integration Points

- **`intercept_user_request`** in `server.py` calls `ContextOptimizer.run(request)` and returns the packed JSON
- **`get_orchestrator_info().advisor_mode`** continues to gate optimization_status enrichment (unchanged)
- Existing `analyze_context_health` and other tools remain unchanged
- `AppContainer` gets a new `get_context_optimizer()` method (optional, for future DI)

## Open Questions

- [ ] Should CRITICAL/HALT also persist the conflict to Engram for future sessions?
- [ ] Does `git diff/log` analysis need a size cap to avoid slow resolution on large repos?
- [ ] Should `ContextOptimizer` be called from `preflight_request` prompt template as well, or only from the explicit tool?
