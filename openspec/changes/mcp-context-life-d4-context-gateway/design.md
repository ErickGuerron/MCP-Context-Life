# Design: MCP Context-Life D4 Context Gateway

## Technical Approach

Convertir Context-Life en un "RAM de Trabajo" técnico que actúa como middleware de ciclo de vida, complementando (no canibalizando) Engram. Implementar el modelo D4 (Decision-Driven Dynamic Delivery) con niveles de intervención basados en salud del contexto.

## Architecture Decisions

### Decision: D4 Engine as Orchestration Layer

**Choice**: `mmcp/orchestration/d4_governance.py` — standalone governance engine that analyzes context health and determines D4 level.

**Alternatives**:
- Embed D4 logic in trim_orchestrator.py (mixes concerns)
- Make it a separate MCP tool (adds latency per call)
- Put in context_slice.py (too granular)

**Rationale**: D4 governance is orchestration-level concern, not context-level. Having it in `orchestration/` follows hexagonal structure and keeps trim strategies as execution details.

### Decision: Technical Metadata Index in RAG

**Choice**: Extend `mmcp/infrastructure/context/rag_engine.py` to store technical metadata alongside chunks.

**Alternatives**:
- Separate metadata store (adds complexity)
- Store in Engram (not always available)
- Hardcode in ContextSlice (not searchable)

**Rationale**: RAG is already indexed by content. Adding metadata fields to the same LanceDB table keeps search and metadata co-located. When Engram is active, RAG serves technical context (code, file_hash) that Engram doesn't index.

### Decision: Pre-Filter Before Vector Search

**Choice**: `search_context` applies SQL-like metadata filters BEFORE vector search.

**Alternatives**:
- Vector search then metadata filter (slower, more candidates)
- Separate metadata index (two sources to sync)
- Fetch all then filter (memory wasteful)

**Rationale**: Pre-filter reduces candidate set significantly. For `type: "code"` queries, filtering 1000 chunks down to 50 before vector search is much faster.

### Decision: D4 Hints in OrchestratorInfo

**Choice**: Add `d4_hints` field to `OrchestratorInfo` returned by `get_orchestrator_info()`.

**Alternatives**:
- Separate `get_d4_status()` tool (extra call)
- Embed in advisor hints (mixes two concerns)
- Return as part of context slice (not orchestrator-level)

**Rationale**: OrchestratorInfo already carries orchestrator detection. Adding `d4_hints` there keeps governance info at the orchestration level where decisions are made.

## Data Flow

### D4 Analysis Flow
```
User message
  → analyze_context_health
      → count tokens, messages
      → determine D4 level (NOP/LIGHT/REQUIRED/CRITICAL)
      → attach hints to OrchestratorInfo
  → If REQUIRED/CRITICAL → apply trim strategy
  → Return enriched context slice
```

### Metadata Index Flow
```
File indexed
  → extract metadata (file_hash, type, task_state)
  → store in LanceDB with chunk
  → searchable by metadata fields

Search request
  → apply metadata filters (type, project, session_id)
  → vector search in filtered subset
  → return with metadata context
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `mmcp/orchestration/d4_governance.py` | Create | D4 engine: analyze + level + hints |
| `mmcp/infrastructure/context/rag_engine.py` | Modify | Add technical metadata to index |
| `mmcp/domain/context_slice.py` | Modify | Add d4_level, file_hash, task_state fields |
| `mmcp/infrastructure/environment/orchestrator_detector.py` | Modify | Add d4_hints to OrchestratorInfo |
| `skills/context-life-integration/SKILL.md` | Modify | D4 integration, fix Engram canibalization |
| `mmcp/infrastructure/environment/config.py` | Modify | Add `d4_governance.enabled`, `d4_governance.level_override` |

## Interfaces / Contracts

```python
# d4_governance.py
class D4GovernanceEngine:
    def analyze(self, messages: list[dict], max_tokens: int) -> D4Level
    def get_hints(self) -> dict  # d4_level, tokens_used, budget_percentage, etc.
    def should_intervene(self) -> bool  # True if NOP/LIGHT, False otherwise

class D4Level(Enum):
    NOP = "NOP"       # tokens < 2000
    LIGHT = "LIGHT"   # 5 <= messages < 15
    REQUIRED = "REQUIRED"  # 15 <= messages < 50
    CRITICAL = "CRITICAL"  # messages >= 50 OR tokens > 80% budget

# context_slice.py additions
class ContextSlice:
    d4_level: D4Level
    file_hash: Optional[str]
    task_state: Optional[str]
    token_cost: int
    summary_objective: Optional[str]
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | D4 level determination logic | Mock messages, assert correct level |
| Unit | Pre-filter reduces candidate count | Index 100 chunks, filter, assert subset size |
| Integration | D4 hints in OrchestratorInfo | Call get_orchestrator_info(), assert d4_hints present |
| E2E | D4 governance with Engram active | Mock Engram, verify both serve different content |

## Migration / Rollback

Feature flags default to `enabled: false` — existing behavior preserved until explicitly enabled.

Rollback: set `d4_governance.enabled: false` to disable.

## Open Questions

- [ ] Should D4 level be persistent across sessions (stored in session.db)?
- [ ] Should we expose D4 level to users via TUI?
- [ ] What is the exact threshold for CRITICAL escalation timing?