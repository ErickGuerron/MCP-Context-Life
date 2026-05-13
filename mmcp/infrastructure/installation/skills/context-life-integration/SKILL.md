---
name: context-life-integration
description: "Trigger: context-life no se invoca solo, subagentes no usan el MCP, integrar con gentle-ai, cómo uso context-life con engram. Decision-driven context prioritization and visible MCP tool invocation for multi-agent pipelines."
license: Apache-2.0
metadata:
  author: erickguerron
  version: "1.0"
---

## Activation Contract

Use this skill when user wants context-life MCP invoked automatically, needs to configure priority with engram, or asks how to integrate context-life with gentle-ai / OpenCode / subagents.

## Hard Rules

1. **NEVER replicate detection logic** — call `context-life/status://orchestrator` or `context-life/get_orchestration_advice` FIRST to know the environment
2. **NEVER modify gentle-ai system prompts** — only give user manual config instructions, be non-intrusive
3. **All context-life tool calls MUST be visible** with `⚙ context-life/[tool_name]` prefix during thinking
4. **Context priority order** (enforced ALWAYS):
   - gentle-ai/engram detected → engram FIRST → context-life → project files
   - standalone → context-life → project files

## Decision Table

| `orchestrator_name` from MCP | Action                                                                                                                                 |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `gentle-ai`                  | Use engram as primary memory, context-life as optimization layer. Give user gentle-ai config instructions (don't modify their prompt). |
| `engram` (no gentle-ai)      | Engram primary → context-life secondary → project files                                                                                |
| `opencode`                   | context-life direct with advisor_mode=true. Show visible tool calls.                                                                   |
| `none`                       | context-life direct → project files                                                                                                    |

## Execution Steps

1. Call `context-life/status://orchestrator` to detect environment
2. Based on `orchestrator_name` result, apply the priority rule from Decision Table
3. For gentle-ai: provide user with config instructions (see Output Contract)
4. For opencode/standalone/subagents: implement visible tool invocation pattern
5. Log all context-life calls with `⚙ context-life/[tool]` prefix

## Trigger Conditions (always invoke context-life)

- Request new from user → `intercept_user_request`
- Tokens > 80% → `analyze_context_health_tool`
- Subagent receives task → `intercept_user_request(advisor_mode=true)`
- Prior work lookup → engram FIRST, then `search_context`

## MCP Installation by Platform

### OpenCode (opencode.json)

```json
"mcp": {
  "context-life": {
    "type": "local",
    "command": ["context-life"],
    "enabled": true
  }
}
```

### Antigravity/Gentle AI

```json
{
  "mcpServers": {
    "context-life": {
      "command": "python",
      "args": ["-m", "mmcp"]
    }
  }
}
```

### Claude Code (CLAUDE.md)

```markdown
## MCP context-life

- Invoke `context-life/intercept_user_request` at start of each task
- Monitor tokens — if > 80%, invoke `context-life/analyze_context_health_tool`
- Show ⚙ context-life/[tool] in each invocation
- Priority: engram → context-life → project files
```

### VS Code (settings.json via MCP extension)

```json
{
  "mcpServers": {
    "context-life": {
      "command": "python",
      "args": ["-m", "mmcp"]
    }
  }
}
```

## System Prompt Addition (for orchestrators)

```
### context-life Priority [OBLIGATORY]

Before responding to any request:
1. If engram available → mem_search (engram) FIRST
2. If not → invoke context-life/get_orchestration_advice
3. If tokens > 80% → invoke context-life/analyze_context_health_tool

Show: ⚙ context-life/[tool_name] for every invocation
```

## Env Vars for context-life

| Variable                       | Value                           | Effect                                          |
| ------------------------------ | ------------------------------- | ----------------------------------------------- |
| `MCP_ORCHESTRATOR`             | `opencode`, `claude_code`, etc. | Activates detection in orchestrator_detector.py |
| `CONTEXT_LIFE_ADVISOR_MODE`    | `true`                          | Forces advisor_mode in subagents                |
| `CONTEXT_LIFE_VISIBILITY`      | `true`                          | Enables ⚙ output                                |
| `CONTEXT_LIFE_TOKEN_THRESHOLD` | `0.8`                           | Threshold for analyze_context_health_tool       |

## References

- `mmcp/infrastructure/environment/orchestrator_detector.py` — detection logic (do not replicate, call via MCP)
- `mmcp/presentation/mcp/server.py` — available tools and `status://orchestrator` resource
