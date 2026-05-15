# context-life-governance Skill & Middleware Specification

## Purpose

This specification defines the strict "Zero-Step" governance rules for context-life auto-invocation. It dictates how the LLM Skills (prompts) and the Python MCP Middleware collaborate to guarantee context optimization happens *before* any core agent task execution.

## Requirements

### Requirement: Solo-Agent "Zero-Step" Wake Behavior (Initialization Lock)

The `context-life.md` skill file MUST inject an absolute system override instructing the solo-agent to fetch memory BEFORE thinking.

#### Scenario: Zero-Step Execution

- GIVEN a solo-agent receives a new user prompt
- WHEN the agent begins its inference
- THEN its ABSOLUTE FIRST token generation MUST be the invocation of `autoinvoke_context(stack_type="solo-agent")`
- AND the agent MUST NOT analyze the prompt, write code, or output conversational text until the tool returns the `ContextPack`.

#### Scenario: Zero-Step with prior state

- GIVEN a solo-agent session with prior state at `~/.config/context-life/sessions/{session_id}/state.json`
- WHEN the agent invokes `autoinvoke_context` as step zero
- THEN the MCP server SHALL merge prior state internally before returning the `ContextPack`
- AND the agent MUST NOT proceed until `ContextPack` is received.

### Requirement: Solo-Agent Sleep Behavior

The `context-life.md` skill MUST enforce explicit persistence instructions.

#### Scenario: Persist state at task end

- GIVEN a solo-agent has completed the user's primary request
- WHEN the execution naturally concludes
- THEN the agent MUST call `sleep_context()` to persist its current learnings to the server.
- AND the agent must treat the chat history as volatile and unreliable.

#### Scenario: Skip sleep if DISABLE_AUTOINVOKE=1

- GIVEN environment has `DISABLE_AUTOINVOKE=1`
- WHEN solo-agent prompt ends
- THEN the agent SHALL NOT call `sleep_context`
- AND normal cleanup proceeds without context-life interference.

### Requirement: Orchestrator-Mediated Handoff Behavior (Zero-Step Routing)

In any stack where the orchestrator supports `delegate()`, governance shifts from the Skill file to the Orchestrator's internal routing rules. The `context-life-advisor` sub-agent is **stack-agnostic** — it works with gentle-ai OR any custom orchestrator that exposes a `delegate(agent, prompt)` mechanism.

Solo-agent hosts (Windsurf, Codex, Claude Code) **cannot** use the advisor pattern because they lack `delegate()` — for these, the Skill approach applies instead.

#### Scenario: Orchestrator Pre-Flight Routing

- GIVEN an orchestrator that supports `delegate()` and stack_type is NOT `solo-agent`
- WHEN the orchestrator receives a new user prompt
- THEN the orchestrator MUST NOT route the prompt to an SDD phase (like `sdd-propose`)
- BUT MUST strictly delegate the raw prompt to the `context-life-advisor` sub-agent FIRST.

#### Scenario: Advisor Tool Execution (Low Latency)

- GIVEN the `context-life-advisor` receives the delegated task
- WHEN it executes
- THEN it SHALL call a single MCP tool: `autoinvoke_context(stack_type="<stack_type>")`
- AND the Python MCP server SHALL handle context extraction and knowledge indexing internally.
- AND the advisor SHALL pass the resulting `ContextPack` back to the orchestrator as ground truth.

#### Scenario: Advisor with no Engram connection

- GIVEN `context-life-advisor` is invoked AND Engram is unreachable
- WHEN `autoinvoke_context` is called
- THEN the MCP server SHALL return `ContextPack` with `context_items: []`
- AND log error for diagnostics
- AND the agent SHALL proceed without context.

### Requirement: Solo-Agent Fallback (No delegate() Support)

Solo-agent hosts do not expose a `delegate()` mechanism. For these environments, the `context-life.md` skill file provides governance via prompt instruction.

#### Scenario: Solo-agent uses skill-based governance

- GIVEN a solo-agent host (Windsurf, Codex, Claude Code) with `context-life.md` loaded
- WHEN the agent receives a new user prompt
- THEN the skill file instructs the agent to call `autoinvoke_context(stack_type="solo-agent")` as its ABSOLUTE FIRST token
- AND the agent MUST NOT proceed until the `ContextPack` is received.

#### Scenario: Custom orchestrator without delegate()

- GIVEN a custom orchestrator that does NOT support `delegate()`
- WHEN the system detects this (no `DELEGATE_SUPPORTED` env var)
- THEN the system SHALL fall back to skill-based governance
- AND load `context-life.md` if available

### Requirement: Skill Availability Fallback & Disabling

The system MUST gracefully step aside if bypassed or unsupported.

#### Scenario: DISABLE_AUTOINVOKE flag set

- GIVEN `DISABLE_AUTOINVOKE=1` is set in the environment
- WHEN the `autoinvoke_context` tool is called
- THEN the MCP server SHALL return a graceful bypass message
- AND the agent SHALL proceed with normal execution without context interference.

## Environment Matrix

| Environment | Orchestrator Supports `delegate()` | Governance Layer | Wake Action | Sleep Action |
|-------------|-----------------------------------|------------------|-------------|--------------|
| solo-agent (Windsurf, Codex, Claude Code) | ❌ NO | SKILL.md (Prompt) | LLM MUST call `autoinvoke_context` as step zero. | LLM MUST call `sleep_context` at task end. |
| gentle-ai | ✅ YES | Orchestrator JSON | Orchestrator MUST route to `context-life-advisor` first. | N/A (Handled via orchestrator phases). |
| Custom orchestrator with delegate() | ✅ YES | Orchestrator JSON | Orchestrator MUST route to `context-life-advisor` first. | N/A (Handled via orchestrator phases). |
| Custom orchestrator without delegate() | ❌ NO | SKILL.md (Prompt) | Same as solo-agent fallback. | Same as solo-agent fallback. |
| solo-agent (DISABLE_AUTOINVOKE=1) | Any | None | No-op | No-op |

## Advisor Stack-Agnostic Design

The `context-life-advisor` sub-agent is designed to be **stack-agnostic**. It requires only:
1. An orchestrator that supports `delegate(agent, prompt)` calls
2. The `autoinvoke_context` MCP tool exposed by context-life server

This means the advisor works identically whether the orchestrator is:
- gentle-ai's orchestrator
- A custom orchestrator you build that exposes `delegate()`
- Any future multi-agent framework that implements `delegate()`

The skill (`context-life.md`) remains the fallback for solo-agent hosts and orchestrators without `delegate()` support.

## Removed

- **Mid-session transitions (Solo ↔ Multi-Agent)**: Deferred to v2. The v1 implementation assumes static stack type for the entire session.
- **Session ID in skill contract**: The skill no longer passes `session_id`. The MCP server derives it server-side.
- **Multi-tool call sequences**: The skill no longer instructs the agent to call `intercept_user_request` then `index_knowledge` then return. The MCP server handles this internally via a single `autoinvoke_context` call.
- **`gentle-ai` as the only multi-agent stack**: The advisor pattern now applies to any orchestrator with `delegate()` support.