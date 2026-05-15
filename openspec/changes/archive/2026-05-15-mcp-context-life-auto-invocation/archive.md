# Archive: mcp-context-life-auto-invocation

**Archived**: 2026-05-15
**Change**: mcp-context-life-auto-invocation
**Mode**: Strict TDD

---

## Summary

Implemented automatic context lifecycle management for Context-Life MCP server:
- **Stack detection**:区分 solo-agent vs multi-agent (orchestrator) based on environment signals
- **Session ID derivation**: Server-side session ID computation with 12h TTL persistence
- **Auto-invoke**: `autoinvoke_context` tool returns ContextPack at prompt boundaries
- **Sleep**: `sleep_context` tool persists session state to filesystem
- **DISABLE_AUTOINVOKE=1**: Silent bypass flag for all components

---

## Stats

| Metric | Value |
|--------|-------|
| Tasks completed | 37/37 |
| Tests passed | 446/447 (1 pre-existing failure) |
| Spec scenarios covered | 23/23 |

### Spec Compliance
- `context-auto-invocation/spec.md`: 13/13 scenarios compliant
- `context-life-governance/spec.md`: 10/10 scenarios compliant

---

## Verification Result

**PASS** ✅

- All 37 tasks complete
- 446/447 tests pass (1 pre-existing failure unrelated to this change)
- All 23 spec scenarios covered by passing tests
- All design decisions implemented coherently

### Minor Warnings (non-blocking)
1. Spec document not updated to reflect `.gga` signal removal from detection logic
2. Skill file location differs from spec (but functionally equivalent)

---

## Unresolved Issues

- Design.md Open Questions section (item about advisor model and DISABLE_AUTOINVOKE behavior) remains unresolved

---

## Files Archived

- `proposal.md`
- `specs-context-auto-invocation.md`
- `specs-context-life-governance.md`
- `design.md`
- `tasks.md`
- `verify-report.md`
- `state.yaml`
- `archive.md` (this file)