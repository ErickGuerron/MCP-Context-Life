# Proposal: Gentle AI Stack Detection — Rigorous Detection with Manual Override

## Intent

Improve orchestrator detection to identify when Context-Life is running alongside a full Gentle AI stack (orchestrator + engram + SDD agents). When automatic detection fails, allow manual configuration via config file.

## Problem Statement

Currently `orchestrator_detector.py` relies on:
- `GENTLE_AI_ACTIVE` env var (explicit but not always set)
- `.gga` workspace artifact (indirect signal)
- `.gemini/` directory (only detects OpenCode, not Gentle AI specifically)

**Gaps**:
1. No detection of engram memory system being active
2. No detection of SDD agents (sdd-explore, sdd-apply, etc.) being available
3. No way to manually override detection when automatic detection fails
4. When detection fails, user gets no visibility into what the MCP client actually supports

## Scope

### In Scope
- Detect if the MCP client has registered SDD-related tools (e.g., `agents-team-lite`, `sdd-*` tools)
- Detect if engram MCP tools are registered (`mem_*` tools)
- Add manual override option in config (`orchestrator_mode: auto|gentle-ai|opencode|engram|none`)
- When auto-detection finds nothing, show a message suggesting manual configuration
- Update `get_orchestrator_info()` to include detected features (engram, sdd, skills, agents)

### Out of Scope
- Changing the package name from `mmcp` to `mcp`
- Changing the default warmup mode from `lazy`
- Bi-directional handshake with orchestrator (future work)

## Detection Strategy

### Layer 1: Tool signature analysis (NEW — simplified approach)

When the MCP client calls Context-Life tools, it passes context hints. We can detect orchestrator type from:

| Signal in tool call | Implies |
|---------------------|---------|
| `intercept_user_request` called with Gentle AI prompt style | Gentle AI orchestrator |
| `preflight_request` being called as first-step policy | Client has preflight setup (OpenCode, Antigravity, etc.) |
| Session has `gentle-ai` or `sdd` topic_key in engram | Engram has SDD session history |
| `get_orchestration_advice` called with high frequency | Orchestrator is actively managing context |

**Implementation**: Track which tools are called and from which context. After N calls, infer the orchestrator type based on call patterns.

Note: MCP protocol does not allow server-side tool registry enumeration — we cannot call `tools/list` from within the server. So we infer from CALL PATTERNS, not from registry.

### Layer 2: Environment variables (existing)
- `GENTLE_AI_ACTIVE=1` → Gentle AI orchestrator
- `ENGRAM=1` → Engram memory system
- `MCP_ORCHESTRATOR=custom` → Generic orchestrator

### Layer 3: Workspace artifacts (existing)
- `.gga` → Gentle AI workspace
- `.gemini/antigravity/` → Gentle AI with Antigravity extension
- `.atl/` → OpenCode workspace
- `.opencode/` → OpenCode workspace

### Layer 4: Config file manual override (NEW)

```toml
[orchestrator]
# auto = detect automatically (default)
# gentle-ai = force Gentle AI stack detection
# opencode = force OpenCode detection
# engram = force Engram-only detection
# none = disable orchestrator detection
mode = "auto"

[orchestrator.features]
# Manually specify which features are available
# Only used when mode is not "auto"
engram = false
sdd = true
skills = true
agents = false
```

### Layer 5: Detection failure message (NEW)

When `mode = "auto"` and no orchestrator is detected:

Show a message in the MCP startup or via `status://orchestrator` resource:

```
No orchestrator detected. If you're using Gentle AI, OpenCode, or another
orchestrator, you can configure it manually in ~/.config/context-life/config.toml:

[orchestrator]
mode = "gentle-ai"  # or "opencode", "engram", etc.
```

## Architecture

### New Dataclass

```python
@dataclass
class OrchestratorFeatures:
    """Detailed features of detected orchestrator."""
    has_engram: bool = False
    has_sdd_agents: bool = False
    has_skills: bool = False
    has_agent_teams: bool = False
    detected_tools: list[str] = field(default_factory=list)

@dataclass
class OrchestratorInfo:
    is_detected: bool = False
    orchestrator_name: str = "none"
    detection_method: str = "none"
    features: OrchestratorFeatures = field(default_factory=OrchestratorFeatures)
    advisor_mode: bool = False
    manual_override: bool = False  # True if config forced detection
```

### New Detection Layer

```python
def _check_mcp_tool_registry() -> Optional[OrchestratorInfo]:
    """
    Check if the MCP client has registered known SDD or orchestrator tools.
    This requires listing available tools via the MCP protocol.
    """
    # Get list of registered tools from MCP client
    # Check for patterns: mem_*, sdd-*, agents-team-lite, etc.
    # Return OrchestratorInfo with populated features
```

### Config Changes

In `config.py`:

```python
@dataclass
class CLConfig:
    # ... existing fields ...

    # --- Orchestrator ---
    orchestrator_mode: str = "auto"  # auto | gentle-ai | opencode | engram | none

    @dataclass
    class OrchestratorFeaturesConfig:
        engram: bool = False
        sdd: bool = False
        skills: bool = False
        agents: bool = False

    orchestrator_features: OrchestratorFeaturesConfig = field(default_factory=OrchestratorFeaturesConfig)
```

### Detection Flow

```
get_orchestrator_info()
   │
   ├─ Read config.orchestrator_mode
   │     │
   │     └─ if mode == "auto":
   │           ├─ _check_env_vars()
   │           ├─ _check_workspace_artifacts()
   │           └─ _check_mcp_tool_registry()  ← NEW
   │     │
   │     └─ if mode != "auto":
   │           └─ Force detection based on mode
   │
   └─ Return OrchestratorInfo with features
```

## Files to Modify

| File | Change |
|------|--------|
| `mmcp/infrastructure/environment/orchestrator_detector.py` | Add `_check_mcp_tool_registry()`, update `OrchestratorInfo` with `OrchestratorFeatures`, support manual override |
| `mmcp/infrastructure/environment/config.py` | Add `orchestrator_mode` and `orchestrator_features` to `CLConfig`, load from TOML |
| `mmcp/presentation/mcp/server.py` | Expose new features in `status://orchestrator` resource |
| `mmcp/presentation/cli/diagnostics.py` | Show detected features in `doctor` output |

## Testing

- Unit test for `_check_mcp_tool_registry()` with mocked tool list
- Unit test for manual override via config
- Integration test: verify detection of engram tools, SDD agents
- Verify graceful message when no orchestrator detected and mode="auto"

## Open Questions

- How to call `tools/list` from within the MCP server (it would need to make an outbound call)?
- Alternative: instead of calling tools/list, check if known tool namespaces exist in the server's registered tools at startup
- Should the detection failure message be shown via TUI, via MCP resource, or via log?

## Rollback Plan

If this feature causes issues:
1. Set `orchestrator_mode = "auto"` reverts to current behavior
2. Removing the `[orchestrator]` section from config.toml restores defaults
3. No changes to the MCP protocol or existing tool outputs