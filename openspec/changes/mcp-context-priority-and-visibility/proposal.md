# Proposal: MCP Context Priority and Visibility

## Intent

When the Gentle AI ecosystem is detected, define an explicit context lookup priority (engram → context-life → project files) and surface all MCP tool calls visibly during thinking, giving users transparency into what memory/knowledge tools are being invoked and in what order.

## Scope

### In Scope
- Define context lookup priority for the gentle-orchestrator: engram → context-life → project files
- Add a visible "⚙ calling..." prefix for MCP tool calls during thinking (e.g., `⚙ engram_mem_search`, `⚙ context-life/search_context`)
- Create a `context_lookup_chain` guidance block that orchestrates the priority sequence
- Support sub-agents self-invoking context-life tools independently for supplemental context
- Handle both primary orchestrator and `-sdd-poor-orquestration` variants

### Out of Scope
- Modifying the MCP protocol or tool schemas
- Changing engram's internal behavior
- Creating new context-life tools (using existing `index_knowledge`, `search_context`, `intercept_user_request`)

## Capabilities

### New Capabilities
- `context-priority-chain`: Priority-based context lookup with explicit fallback sequencing and visible tool-call indicators
- `mcp-tool-visibility`: Mechanism to surface MCP tool invocations during thinking with a standardized prefix format

## Approach

### 1. Context Lookup Chain

Create a priority chain guidance block for the gentle-orchestrator system prompt:

```
Context Lookup Priority (execute in order):
1. ENGRAM (if detected) → call engram_mem_context
   - Only proceed if result is empty
2. CONTEXT-LIFE (if engram returned nothing) → call context-life tools
   - index_knowledge, search_context, intercept_user_request
   - Sub-agents may invoke independently
   - Only proceed if result is empty
3. PROJECT FILES (final fallback) → read project files directly
   - Openspec specs, skill registry, source files
```

### 2. Visible Tool Call Protocol

When executing any MCP tool in the chain, prefix the thinking output with a visible indicator:

```
⚙ engram_mem_context → found 3 observations
⚙ context-life/search_context → found 0 results (empty)
⚙ context-life/index_knowledge → indexed 12 files
→ Falling back to project files...
```

Format: `⚙ {tool_name}` with arrow suffix showing result summary.

### 3. Sub-Agent Self-Invocation

Allow sub-agents to call context-life tools directly:
- Sub-agents check `get_orchestrator_info()` for `gentle-ai` mode
- If gentle-ai, sub-agents may call `index_knowledge`, `search_context`, `intercept_user_request` independently
- This supplements the orchestrator's primary chain without breaking priority

### 4. Variant Handling

For `-sdd-poor-orquestration` variant:
- Still honor the priority chain
- Tool visibility may be reduced if advisor_mode is false
- Core priority logic remains the same

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `mmcp/infrastructure/environment/orchestrator_detector.py` | Modified | Add `context_lookup_chain` guidance text and visibility flags |
| `mmcp/presentation/mcp/server.py` | Modified | Add visible tool-call prefix mechanism for MCP responses |
| `docs/orchestrator-integration.md` | Modified | Document the priority chain and visibility protocol |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Visibility output clutters thinking | Medium | Only show tool name + arrow + result count (one line per call) |
| Sub-agents over-query context-life | Medium | Limit sub-agent self-invocation to once per major phase |
| Priority chain causes latency on empty results | Low | Early-exit: stop chain as soon as any layer returns results |
| `-sdd-poor-orquestration` variant misses advisor_mode | Low | Detect variant via orchestrator_name field; apply conditional visibility |

## Rollback Plan

1. Remove the `context_lookup_chain` block from orchestrator prompt
2. Disable visible tool-call prefix via config flag `show_mcp_calls: false`
3. Revert `server.py` to pre-change behavior (no prefix output)
4. No changes to existing tool schemas or protocol

## Dependencies

- `engram_mem_context`, `mem_search`, `mem_get_observation` (Engram MCP tools)
- `index_knowledge`, `search_context`, `intercept_user_request` (context-life MCP tools)
- `get_orchestrator_info()` for advisor_mode detection

## Success Criteria

- [ ] Gentle AI orchestrator follows engram → context-life → project files priority
- [ ] All MCP tool calls display visible `⚙ {tool_name}` prefix during thinking
- [ ] Chain stops early when any layer returns non-empty results
- [ ] Sub-agents can invoke context-life tools independently in gentle-ai mode
- [ ] `-sdd-poor-orquestration` variant respects same priority chain
- [ ] Visibility can be disabled via config without breaking priority logic
