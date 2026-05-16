# Delta for skill-integration-correction

## Purpose

Correct the `context-life-integration` skill to implement D4 governance and stop canibalizing Engram.

## MODIFIED Requirements

### Requirement: D4 Integration in Skill

The skill MUST invoke `context-life/analyze_context_health_tool` at prompt boundaries to determine D4 level.

Priority order when Engram is detected:
1. Engram → long-term memory (history, decisions)
2. Context-Life → technical context (D4 governance, code, task states)

#### Scenario: D4 applied with Engram active

- GIVEN `orchestrator_name: "gentle-ai"` and Engram has results
- WHEN user sends a technical query about code
- THEN Context-Life RAG serves code-specific context
- AND D4 level is determined for governance

### Requirement: Visible Tool Invocation

All Context-Life tool calls MUST show `⚙ context-life/[tool_name]` prefix.

Context-Life tools are invoked when:
- `intercept_user_request` at start of each task
- `analyze_context_health_tool` when tokens > 80%
- `optimize_messages` for D4 governance (REQUIRED/CRITICAL levels)
- `search_context` for technical queries

#### Scenario: Visible tool call

- GIVEN context is CRITICAL level
- WHEN `optimize_messages` is called
- THEN response includes `⚙ context-life/optimize_messages`

## REMOVED Behavior

### Removed: "If Engram finds context, Context-Life does nothing"

OLD behavior:
```
gentle-ai detected → engram FIRST → if finds → context-life = code dead
```

NEW behavior:
```
gentle-ai detected → Engram for history
                 → Context-Life for technical/D4 governance
                 → Both active, complementary
```

## Edge Cases

### Requirement: Context-Life Standalone Mode

If Engram is NOT available, Context-Life operates as primary memory with full D4 governance.

#### Scenario: Engram not available

- GIVEN Engram MCP is not connected
- WHEN `search_context` is called
- THEN Context-Life RAG serves all queries
- AND D4 governance applies normally