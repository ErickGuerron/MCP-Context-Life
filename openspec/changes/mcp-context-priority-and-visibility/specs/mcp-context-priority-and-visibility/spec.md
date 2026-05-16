# Delta for MCP Context Priority and Visibility

## Summary

Defines context lookup priority (engram → context-life → project files) and MCP tool-call visibility during thinking via "⚙" prefix.

---

## ADDED Requirements

### Requirement: Context Lookup Priority Chain

When the Gentle AI ecosystem is detected, the orchestrator SHALL follow an explicit three-tier context lookup priority:

1. **ENGRAM** — Call `engram_mem_context` first. Stop chain if results are non-empty.
2. **CONTEXT-LIFE** — If engram returned empty, call `context-life/search_context` or `index_knowledge`. Stop if non-empty.
3. **PROJECT FILES** — If both above returned empty, fall back to reading project files directly (openspec specs, skill registry, source files).

The system MUST stop the chain immediately upon any layer returning non-empty results.

#### Scenario: Engram returns results (chain stops early)

- GIVEN Gentle AI orchestrator is active
- WHEN a user request is received
- THEN the system SHALL call `engram_mem_context` first
- AND if results are found, SHALL skip context-life and project file lookup
- AND display `⚙ engram_mem_context → found N observations`

#### Scenario: Engram empty, context-life returns results

- GIVEN Gentle AI orchestrator is active
- AND `engram_mem_context` returned empty
- WHEN the user request is processed
- THEN the system SHALL call `context-life/search_context`
- AND if results are found, SHALL skip project file lookup
- AND display `⚙ context-life/search_context → found N results`

#### Scenario: Both engram and context-life empty, project files as fallback

- GIVEN Gentle AI orchestrator is active
- AND both engram and context-life returned empty
- WHEN the user request is processed
- THEN the system SHALL read project files directly
- AND display `→ Falling back to project files...`

---

### Requirement: MCP Tool Visibility Prefix

During thinking, the system SHALL display all MCP tool calls with a visible `⚙ {tool_name}` prefix followed by an arrow and result summary.

The format SHALL be: `⚙ {tool_name} → {result_summary}`

#### Scenario: Visible tool call for engram_mem_search

- GIVEN the context lookup chain is executing
- WHEN `engram_mem_search` is called
- THEN the system SHALL display `⚙ engram_mem_search → found N observations`
- AND this SHALL appear within the thinking output before proceeding

#### Scenario: Visible tool call for context-life index_knowledge

- GIVEN the context lookup chain reaches context-life tier
- WHEN `index_knowledge` is called
- THEN the system SHALL display `⚙ context-life/index_knowledge → indexed N files`

#### Scenario: Tool visibility can be disabled via config

- GIVEN the system configuration has `show_mcp_calls: false`
- WHEN MCP tools are invoked
- THEN the system SHALL NOT display the `⚙` prefix
- AND the priority chain behavior SHALL remain unchanged

---

### Requirement: Sub-Agent Self-Invocation for context-life

In gentle-ai mode, sub-agents SHALL be permitted to invoke context-life tools independently for supplemental context, without disrupting the orchestrator's primary priority chain.

Sub-agents SHALL check `get_orchestrator_info()` for `gentle-ai` mode before self-invocation. Sub-agent self-invocation SHALL be limited to once per major phase to prevent over-querying.

#### Scenario: Sub-agent invokes context-life independently in gentle-ai mode

- GIVEN a sub-agent is active in a gentle-ai session
- WHEN the sub-agent calls `context-life/search_context` directly
- THEN the system SHALL process the supplemental query
- AND SHALL display `⚙ context-life/search_context (sub-agent) → found N results`
- AND this SHALL NOT affect the orchestrator's primary priority chain

#### Scenario: Sub-agent self-invocation limited per phase

- GIVEN a sub-agent is active in a major phase (e.g., design, apply)
- WHEN the sub-agent has already invoked context-life once in this phase
- THEN the system SHALL NOT allow another self-invocation until the next phase

---

### Requirement: Variant Handling for -sdd-poor-orquestration

The system SHALL honor the same context lookup priority for the `-sdd-poor-orquestration` variant, but tool visibility MAY be reduced when `advisor_mode` is false.

#### Scenario: -sdd-poor-orquestration variant respects priority chain

- GIVEN the orchestrator_name field indicates `-sdd-poor-orquestration`
- WHEN a user request is processed
- THEN the system SHALL still follow engram → context-life → project files priority
- AND tool visibility MAY be reduced based on advisor_mode

---

### Requirement: Trigger Conditions for MCP Tool Activation

Each MCP tool in the priority chain SHALL activate based on specific conditions:

| Tool | Trigger Condition | Fallback Behavior |
|------|-------------------|-------------------|
| `engram_mem_context` | Gentle AI orchestrator detected | Skip to context-life |
| `engram_mem_search` | Explicit user query about past work | Skip to context-life |
| `context-life/search_context` | Engram returned empty AND gentle-ai mode | Skip to project files |
| `context-life/index_knowledge` | Sub-agent request OR cold-start pre-warm | No fallback (final) |
| `context-life/intercept_user_request` | User request normalization requested | Continue chain |

#### Scenario: engram_mem_search triggers on "remember" queries

- GIVEN the user says "remember what we did with auth"
- WHEN the request is parsed
- THEN the system SHALL call `engram_mem_search` with relevant keywords
- AND display `⚙ engram_mem_search → found N observations`

#### Scenario: context-life intercept_user_request triggers for request normalization

- GIVEN a user request requires normalization before routing
- WHEN `intercept_user_request` is called
- THEN the system SHALL display `⚙ context-life/intercept_user_request → normalized`
- AND continue the priority chain

---

## MODIFIED Requirements

None. This change introduces new capabilities without modifying existing requirements.

## REMOVED Requirements

None.