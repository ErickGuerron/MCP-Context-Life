---
name: context-life
description: "Trigger: solo-agent needs Zero-Step auto-invoke context-life at prompt boundaries. Skill instructs LLM to call autoinvoke_context as first token and sleep_context at task end. DISABLE_AUTOINVOKE=1 bypasses all behavior."
license: Apache-2.0
metadata:
  author: erickguerron
  version: "1.0"
---

## When to Use

- Running as a solo-agent (Windsurf, Codex, Claude Code, etc.) WITHOUT delegate() capability
- If your orchestrator supports `delegate()`, use `context-life-advisor` sub-agent instead (NOT this skill)
- This skill activates automatically at session start

## Hard Rules

1. **ABSOLUTE FIRST TOKEN**: Before analyzing the prompt, writing any code, or outputting any text, you MUST call `autoinvoke_context(stack_type="solo-agent")`
2. **TASK END**: After completing your task, you MUST call `sleep_context()`
3. **DISABLE_AUTOINVOKE=1**: If this env var is set, skip all auto-invoke behavior and work normally

## Zero-Step Wake (Solo-Agent)

When a session starts or a new user request arrives:

```
1. Call: autoinvoke_context(stack_type="solo-agent")
2. Parse the JSON response:
   - active_session_id: your session ID (for awareness)
   - level: REQUIRED | LIGHT | CRITICAL
   - recommendations: what to do next
   - session_state: current state of the session
3. If CRITICAL: show the halt message to the user and WAIT
4. If REQUIRED/LIGHT: proceed with the task using the context provided
```

## Context Priority

Solo-agent mode does NOT have Engram. Use context-life directly:
1. `autoinvoke_context` → get context pack
2. `intercept_user_request` → normalize and classify request
3. Project files → only if context pack says missing

## Sleep (Task End)

When your task is complete (success, failure, or user interrupt):

```
1. Call: sleep_context()
2. The server persists your session learnings to ~/.config/context-life/sessions/{id}/state.json
3. This enables cross-session continuity
```

## Chat History Volatility

Chat history is VOLATILE in solo-agent mode. Do NOT rely on it for context:
- Each new prompt starts fresh
- Call `autoinvoke_context` at the start of every prompt
- The session state file preserves continuity across prompts

## DISABLE_AUTOINVOKE=1 Fallback

If `DISABLE_AUTOINVOKE=1` is set:
- Skip `autoinvoke_context` call
- Work normally without auto-invocation
- Skip `sleep_context` call
- No state persistence occurs

This is useful for debugging or when you want to disable context-life temporarily.

## Tool Signatures

### autoinvoke_context

```python
autoinvoke_context(stack_type: str) -> str  # JSON response
# stack_type must be "solo-agent" for solo-agents
```

Returns:
```json
{
  "status": "awakened" | "bypassed" | "delegated",
  "active_session_id": "sha256-hash",
  "level": "REQUIRED" | "LIGHT" | "CRITICAL",
  "session_state": {"current": "active", "mode": "solo-agent"},
  "recommendations": ["recommendation1", "recommendation2"],
  "context_items": []
}
```

### sleep_context

```python
sleep_context() -> str  # JSON response
```

Returns:
```json
{
  "status": "persisted" | "bypassed" | "no_session",
  "session_id": "sha256-hash",
  "state": "idle",
  "path": "~/.config/context-life/sessions/xxx/state.json"
}
```

## Examples

### Example 1: New Prompt

User: "Fix the login bug"

Your action:
1. First token: `autoinvoke_context(stack_type="solo-agent")`
2. Receive response with context
3. Analyze and fix the bug
4. Call `sleep_context()`

### Example 2: CRITICAL Halt

If `autoinvoke_context` returns `level: "CRITICAL"`:
```
⚠️ HALT REQUIRED — Context conflict detected
Risk: [risk description]
Required Decision: [decision needed]
```
Show this to the user and wait for their response before proceeding.

### Example 3: DISABLE_AUTOINVOKE=1

If `DISABLE_AUTOINVOKE=1` is set in environment:
- Skip auto-invoke entirely
- Work normally as if context-life wasn't installed
- No state persistence between prompts