---
name: contexto-life-docs
description: >
  Define what documentation belongs in `docs/` for the Context-Life project and how to write it quickly without lying to the codebase.
  Trigger: when documenting features, usage, operations, architecture, metrics, or deciding whether content belongs in `docs/` vs `openspec/specs/`.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- When adding or updating project documentation.
- When deciding if content is user docs, maintainer docs, or planning/spec material.
- When docs must stay aligned with the current codebase and avoid stale claims.

## Project Context

- Project: `mcp-context-life`
- Stack: Python 3.10+ MCP server (`mmcp/`), `pytest`, `ruff`, hybrid `openspec/` SDD.
- Canonical split:
  - `docs/` = current behavior, usage, operations, reference, explanation.
  - `openspec/specs/` = proposals, RFCs, benchmarks, planning, task breakdowns.

## Critical Patterns

### 1) Folder decision rule

| Content type | Goes to | Why |
|---|---|---|
| Quickstart, installation, CLI usage, config reference | `docs/` or `README.md` | User-facing and current-state docs |
| Feature guide, workflow, troubleshooting, runbook | `docs/` | Explains how the product works now |
| Architecture overview, protocol notes, operational limits | `docs/` | Helps users/maintainers understand behavior |
| RFCs, proposals, metrics plans, benchmark analysis, task plans | `openspec/specs/` | Planning, not documentation |

### 2) Write docs like Living Documentation

- Every claim must reflect current code or config.
- If a doc says how something works, include exact file/module names when useful.
- Never leave aspirational wording unless it is clearly labeled as planned.
- If code and docs diverge, fix the doc or flag the mismatch explicitly.

### 3) Product-first structure

- Start with the user goal, not with internal implementation.
- Prefer task-oriented headings: install, connect, inspect, troubleshoot.
- Show examples before explanations when that reduces friction.

### 4) Self-documentation first

- Reuse clear names from the code instead of inventing new terms.
- Do not explain obvious code; explain decisions, boundaries, and tradeoffs.
- Keep prose tight; if a sentence does not help the reader act, remove it.

### 5) Docs-for-developers metrics

- When documenting performance or behavior, include measurable facts: latency, budget, cache hit patterns, counts, constraints.
- Prefer baseline → change → result.
- Mention what is verified vs what is only proposed.

## Writing Workflow

1. Identify the audience: end user, operator, or maintainer.
2. Ask only the minimum questions needed if context is missing.
3. Check the current source of truth first: `README.md`, `pyproject.toml`, `openspec/config.yaml`, and the touched module(s).
4. Write the doc in the smallest file that fits the audience.
5. Add links to code paths or commands only when they reduce ambiguity.

## Minimum Questions When Context Is Missing

Ask these, one at a time, and stop:

1. Who is this doc for: end user, operator, or maintainer?
2. Is this current behavior or planned behavior?
3. Which action should the reader be able to complete after reading it?
4. Which code paths or commands are the source of truth?

## Commands

```bash
pytest
ruff check
ruff format
```

## Resources

- `README.md` — top-level user entry point.
- `openspec/config.yaml` — SDD rules and canonical doc split.
- `openspec/specs/` — planning artifacts that should not be copied into `docs/`.
- `mmcp/` — implementation source of truth.
