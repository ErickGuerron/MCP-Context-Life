# Context Orchestration — Adaptive to Your Stack

Context-Life can detect and adapt to AI orchestration systems like Gentle AI, automatically optimizing how context flows between the user, the orchestrator, and the underlying agents.

---

## Quick Path

1. **Detection**: Context-Life auto-detects orchestrators via environment variables and workspace artifacts
2. **Classification**: D4 (Intelligent Context Optimization) evaluates every prompt
3. **Adaptation**: The orchestration layer receives the right context budget and action hints
4. **Verification**: All decisions are logged and reversible

---

## How Orchestrator Detection Works

Context-Life detects orchestrators using two mechanisms:

### Environment Variables

| Variable | What It Triggers |
|----------|------------------|
| `GENTLE_AI_ACTIVE=1` | Gentle AI orchestrator detected → Advisor Mode active |
| `ENGRAM=1` | Engram memory system active |
| `MCP_ORCHESTRATOR=1` | Generic MCP orchestrator detected |

### Workspace Artifacts

Context-Life checks for these directories/files in the project root:

| Artifact | Detection |
|----------|-----------|
| `.gga` | Gentle AI active workspace |
| `.gemini/` | Google Gemini workspace |
| `.agent/` or `.agents/` | Agent workspace directory |
| `.mcp/` | MCP configuration directory |

When any of these are present, **Advisor Mode** is activated automatically.

---

## Advisor Mode

When Advisor Mode is active, Context-Life adds optimization hints to tool responses:

```json
{
  "advisor_hints": {
    "orchestrator": "gentle-ai",
    "should_trim_now": true,
    "suggested_strategy": "smart",
    "prefix_stable": false,
    "dynamic_token_ratio": 0.72,
    "recommendation": "Static prefix changed — cache miss expected this turn."
  }
}
```

These hints tell the orchestrator:
- Whether the static prefix is stable (affects cache reuse)
- How aggressive to be with trimming
- What strategy to use for `optimize_messages`

---

## How Context Flows Through the Stack

```
User's Raw Prompt
       │
       ▼
┌──────────────────────────────────────┐
│       intercept_user_request          │
│  ┌───────────────────────────────┐   │
│  │   D4: Context Optimization     │   │
│  │   ├─ LIGHT / REQUIRED / CRITICAL│   │
│  │   └─ confidence + next_action   │   │
│  └───────────────────────────────┘   │
│              │                        │
│              │ (merged into response) │
│              ▼                        │
│  ┌───────────────────────────────┐   │
│  │   Gentle AI Orchestrator       │   │
│  │   (sdd-orchestrator)           │   │
│  │   ├─ Decides next sub-agent    │   │
│  │   ├─ Passes context to agents  │   │
│  │   └─ Controls context budget   │   │
│  └───────────────────────────────┘   │
│              │                        │
│              ▼                        │
│  ┌───────────────────────────────┐   │
│  │   SDD Sub-Agents               │   │
│  │   (sdd-explore, sdd-apply, ...)│   │
│  │   Receive compact context      │   │
│  │   Work in isolated windows     │   │
│  └───────────────────────────────┘   │
```

**Key principle**: D4 does NOT replace the orchestrator. It generates the **context pack** that the orchestrator uses to make decisions. The orchestrator controls what each sub-agent receives.

---

## What Each Component Does

| Component | Role | Inputs | Outputs |
|-----------|------|--------|---------|
| `autoinvoke_context` | Zero-step wake at prompt boundaries | `stack_type` (solo-agent/orchestrator) | `ContextPack` with context items, session state, recommendations, active_session_id |
| `intercept_user_request` | Pre-processor | Raw prompt | Legacy contract + D4 decision |
| `get_orchestration_advice` | Orchestrator advisor | Message array | Health + recommended tool |
| `ContextOptimizer` (D4) | Classifier | Prompt | {state, confidence, context_budget, next_action} |
| `ConflictDetector` | Contradiction checker | Prompt + project files | Conflict report or None |
| `sleep_context` | Persist session learnings | Session state | Confirmation + persisted state |

---

## Gentle AI Integration

Gentle AI uses Context-Life as part of its SDD (Spec-Driven Development) workflow:

1. **User sends prompt** → `intercept_user_request` classifies it
2. **If LIGHT**: Orchestrator proceeds to `sdd-explore` or `sdd-propose`
3. **If REQUIRED**: Orchestrator fetches context via `cache_context` or asks user
4. **If CRITICAL**: Orchestrator shows HALT with conflict details and waits for user decision

### SDD Context Flow

```
User: "Add login to my React app"
       │
       ▼ D4 classifies: LIGHT (clear goal, explicit files, stack mentioned)
       │
       ▼ Orchestrator passes to sdd-propose
       │
       ▼ sdd-propose generates proposal
       │
       ▼ Orchestrator passes to sdd-apply (with context budget: small)
       │
       ▼ Implementation runs with context optimized for React + FastAPI
```

---

## What D4 Does NOT Do

- **Does NOT replace `sdd-init`**: SDD context is set up once per project, not on every prompt
- **Does NOT replace Engram**: Memory persists across sessions independently
- **Does NOT replace the orchestrator**: The orchestrator decides what to do with D4's output
- **Does NOT auto-modify prompts**: D4 recommends, the orchestrator decides

---

## Auto-Invoke Context Lifecycle (Zero-Step)

Context-Life implements a **Zero-Step** governance model that guarantees context optimization happens *before* any agent task execution.

### Environment Matrix

| Environment | Orchestrator Supports `delegate()` | Governance Layer | Wake Action | Sleep Action |
|-------------|-----------------------------------|------------------|-------------|--------------|
| solo-agent (Windsurf, Codex, Claude Code) | ❌ NO | `context-life` skill (prompt) | LLM MUST call `autoinvoke_context` as step zero | LLM MUST call `sleep_context` at task end |
| gentle-ai | ✅ YES | Orchestrator JSON | Orchestrator MUST route to `context-life-advisor` first | N/A (Handled via orchestrator phases) |
| Custom orchestrator with `delegate()` | ✅ YES | Orchestrator JSON | Orchestrator MUST route to `context-life-advisor` first | N/A (Handled via orchestrator phases) |
| Custom orchestrator without `delegate()` | ❌ NO | `context-life` skill (prompt) | Same as solo-agent fallback | Same as solo-agent fallback |
| solo-agent (`DISABLE_AUTOINVOKE=1`) | Any | None | No-op | No-op |

### Session ID Derivation (Server-Side)

The MCP server derives `session_id` deterministically without relying on LLM input:

1. IF `ENGRAM_SESSION_ID` environment variable exists → use it directly
2. ELSE IF `.context-session.id` file exists in `cwd` and is < 12 hours old → read its value
3. ELSE compute new hash from `cwd + current_timestamp`, save to `.context-session.id`, use it

### DISABLE_AUTOINVOKE Bypass

Set `DISABLE_AUTOINVOKE=1` in the environment to disable all auto-invocation behavior silently. All components respect this flag and proceed without context interception.

### Advisor Stack-Agnostic Design

The `context-life-advisor` sub-agent is **stack-agnostic**. It requires only:
1. An orchestrator that supports `delegate(agent, prompt)` calls
2. The `autoinvoke_context` MCP tool exposed by Context-Life

This means the advisor works identically whether the orchestrator is gentle-ai's orchestrator or any custom orchestrator you build that exposes `delegate()`.

---

## Configuration

### For Gentle AI Users

No extra configuration needed. Context-Life auto-detects Gentle AI via:
- `GENTLE_AI_ACTIVE` environment variable
- `.gga` workspace artifact

### For Custom Orchestrators

Set the `MCP_ORCHESTRATOR` environment variable:

```bash
export MCP_ORCHESTRATOR=1
```

Or create a `.agents/` directory in your project root.

---

## Tool Integration

Context-Life exposes these tools for orchestrator integration:

| Tool | Purpose |
|------|---------|
| `autoinvoke_context` | Zero-step wake — returns ContextPack at prompt boundaries (solo-agent or orchestrator) |
| `sleep_context` | Persist session learnings at task end (solo-agent sleep) |
| `intercept_user_request` | Normalize and classify any user prompt |
| `get_orchestration_advice` | Get next-step recommendation with health metrics |
| `analyze_context_health_tool` | Get health score for current message array |
| `cache_context` | Fetch project context with cache awareness |
| `optimize_messages` | Trim message array when needed |

---

## Status Resources

Context-Life exposes orchestration status via MCP resources:

| Resource | What It Returns |
|----------|-----------------|
| `status://orchestrator` | Detected orchestrator name and advisor mode status |
| `status://orchestration` | Static contract and recommended tool flow |
| `status://token_budget` | Current budget and LRU cache stats |

---

## Open Items

- **Bidirectional handshake**: Current integration is one-way (Context-Life → orchestrator). Future versions may support orchestrator callbacks.
- **Heuristic advisor**: Advisor Mode currently uses heuristics. A learning mode based on acceptance/rejection patterns is planned.