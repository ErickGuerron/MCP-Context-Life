---
name: contexto-life-planning-rigor
description: >
  Plan and specify Context-Life changes rigorously with structured tables, explicit requirements, and low-ambiguity decisions.
  Trigger: when creating PRDs, RFCs, designs, change requests, story maps, or any planning/specification that must reduce AI mistakes.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- When a request needs analysis before code changes.
- When requirements are ambiguous, broad, or high-risk.
- When the output must become a PRD, RFC, design, or implementation plan.
- When you need a table-first format that makes gaps obvious.

## Project Context

- Project: `mcp-context-life`
- Stack: Python 3.10+ MCP server, hybrid SDD, `openspec/specs/` for planning.
- Canonical rule: planning artifacts live in `openspec/specs/`; docs live in `docs/`.

## Critical Patterns

### 1) Plan before solution

- Start from the user problem, not the implementation.
- Separate symptom, goal, scope, and constraints.
- Never jump to code until the change is decomposed.

### 2) Use tables as the source of truth

- Always represent requirements, requests, assumptions, and open questions in tables.
- Every row must have one responsibility.
- Keep statuses explicit: `proposed`, `confirmed`, `blocked`, `out of scope`.

### 3) Be ruthless about ambiguity

- If context is missing, ask the minimum one question at a time and stop.
- Do not infer business rules silently.
- If a requirement is vague, rewrite it as a testable statement or mark it as unknown.

### 4) Design for cognition, not prose

- Prefer short sections with headings: problem, goals, non-goals, requirements, risks, decisions, next steps.
- Use bullets only for details; the table should carry the structure.
- Keep one idea per paragraph.

### 5) Reduce AI error rate

- Make boundaries explicit: what changes, what does not, and what must remain stable.
- Call out dependencies, side effects, rollback needs, and verification points.
- Prefer concrete nouns from the codebase over generic terms.

## Required Table Shapes

### Change Request Table

| Field | Content |
|---|---|
| Request | What the user wants |
| Problem | Why this is needed |
| Scope | What will change |
| Non-goals | What will not change |
| Constraints | Technical/product limits |
| Risks | What can go wrong |
| Success criteria | How we know it worked |

### Requirements Table

| ID | Requirement | Priority | Type | Verification |
|---|---|---:|---|---|
| R1 | Clear, testable requirement | High/Med/Low | Functional/Non-functional | How to verify |

### Decisions Table

| Decision | Options considered | Chosen | Rationale |
|---|---|---|---|

### Questions Table

| Question | Why it matters | Blocking? |
|---|---|---|

## Planning Workflow

1. Capture the request in one sentence.
2. Convert it into a structured change table.
3. Split requirements into must/should/could.
4. Identify missing context and ask only the blocking questions.
5. Produce a concise plan with risks and verification.
6. Keep planning artifacts in `openspec/specs/`.

## Default Output Order

1. Summary
2. Change Request Table
3. Requirements Table
4. Decisions Table
5. Risks / tradeoffs
6. Open questions
7. Next actions

## Commands

```bash
pytest
ruff check
ruff format
```

## Resources

- `openspec/specs/` — planning/RFC home.
- `openspec/config.yaml` — hybrid SDD rules.
- `README.md` — current product summary.
- `docs/` — only current, user-facing documentation.
