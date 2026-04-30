# RFC-003: Telemetry, Budget Integrity, and Scalable Usage Accounting

**Status**: Proposed  
**Author**: OpenCode  
**Date**: 2026-04-04  
**Scope**: Telemetry, token budget governance, model accounting, scalability

## 1. Summary

This RFC proposes the next architectural step for Context-Life after the benchmark and budget review dated `2026-04-04`.

The current platform already has a solid operational base:

- benchmark execution is stable,
- trim stays within budget in verified scenarios,
- cache prefix reuse works,
- RAG selection under token limits works,
- model/provider detection is present,
- telemetry is persisted and exposed in the CLI/TUI.

However, the system still has a **trust gap** in the most strategic metric: **how many tokens were actually consumed per model and how much of the runtime budget was truly spent**.

Today the project can show usage, savings, and budget views, but it cannot yet guarantee that these numbers mean the same thing across all tools or that they scale cleanly as more runtime capabilities are added.

This RFC closes that gap by defining:

1. a **canonical token semantics model**,
2. an **integral runtime budget policy**,
3. a **scalable telemetry aggregation contract**,
4. an **end-to-end benchmark and verification suite** for telemetry correctness.

## 2. Motivation

The benchmark-budget analysis in `docs/benchmark-budget-analysis-2026-04-04.md` confirmed that the product is functionally healthy, but also documented three structural issues that block trustworthy scaling.

### 2.1 Budget is visible, but not integral

Verified in `mmcp/server.py`:

- `count_tokens_tool()` consumes `_token_budget`.
- `count_messages_tokens_tool()` consumes `_token_budget`.
- `optimize_messages()`, `search_context()`, `cache_context()`, `analyze_context_health_tool()`, and `get_orchestration_advice()` do **not** consume `_token_budget` directly.

That means the current budget behaves as a **local counter for selected tools**, not as a full runtime budget ledger.

### 2.2 Weekly per-model usage is not semantically safe yet

Verified in `mmcp/session_store.py`:

- weekly and all-time totals use `SUM(input_tokens + output_tokens)`.

Verified in `mmcp/telemetry_service.py`:

- for `cache_context`, telemetry extraction sets:
  - `input_tokens = total_tokens`
  - `output_tokens = total_tokens`

This creates a concrete risk of **double counting** for cache events, which means the current `used` metric can overstate consumption.

### 2.3 The benchmark validates behavior, but not accounting correctness end-to-end

The current benchmark validates runtime behavior such as trim, cache hits, and RAG selection, but it does not yet assert:

- telemetry event correctness by tool type,
- aggregation correctness across heterogeneous events,
- budget tracker correctness across the runtime,
- dashboard correctness against canonical accounting rules.

That is the real reason the current numbers are useful for observation, but not yet safe as a final cost or capacity metric.

## 3. Problem Statement

Context-Life needs a telemetry and budget architecture that remains correct when the project keeps growing.

Without a canonical contract, every new tool can silently introduce one of these failures:

- inconsistent token meaning,
- partial budget coverage,
- double counting,
- misleading dashboard totals,
- invalid optimization decisions driven by noisy metrics.

This is not just a QA cleanup. It is a **scalability problem**:

- more tools will produce more event types,
- more orchestrators will depend on these numbers,
- more dashboards and decisions will be built on top of this telemetry,
- any semantic ambiguity today compounds into product debt tomorrow.

## 4. Goals

### 4.1 Primary goals

1. Define one authoritative meaning for token usage fields.
2. Eliminate double counting in weekly and all-time usage aggregation.
3. Expand budget tracking from “selected counters” to an explicit runtime policy.
4. Make dashboard numbers defensible and explainable.
5. Add end-to-end verification so future tools cannot break accounting silently.

### 4.2 Secondary goals

1. Keep the architecture simple enough for a local-first MCP server.
2. Preserve backwards compatibility where possible for existing CLI/TUI views.
3. Enable future reporting dimensions such as per-tool, per-provider, and per-operation analysis.

## 5. Non-Goals

This RFC does **not** attempt to:

- calculate real provider billing in dollars,
- predict vendor-side prompt-cache billing semantics,
- redesign the entire telemetry UI,
- replace SQLite.

This RFC is about **correct accounting semantics and scalable instrumentation**, not external pricing.

## 6. Current State Evidence

### 6.1 What is already working well

From `docs/benchmark-budget-analysis-2026-04-04.md`:

- benchmark execution is stable,
- trim scenarios were verified within budget,
- stable-prefix cache behavior is correct,
- RAG indexing and limited retrieval are functioning,
- model detection and persistence are present,
- relevant tests are green,
- TUI telemetry panels are already useful.

This matters because we are **not** rebuilding from zero. We are hardening a system that already demonstrates product value.

### 6.2 What is blocking trustworthy scaling

The same analysis explicitly warns that:

- the global budget is not consumed by all relevant tools,
- the benchmark does not validate telemetry or budget end-to-end,
- total weekly usage mixes metrics with non-homogeneous meaning,
- `cache_context` may be double counted in model usage totals.

That warning is correct and the code confirms it.

## 7. Proposed Changes

### P1. Canonical Usage Semantics

Introduce a strict telemetry contract for every `UsageEvent`.

#### New semantic model

Each event must classify tokens into explicit buckets:

- `observed_input_tokens`: tokens inspected or processed by the tool
- `observed_output_tokens`: tokens emitted or returned by the tool
- `billable_input_tokens`: tokens that should count as prompt-side effective usage
- `billable_output_tokens`: tokens that should count as completion-side effective usage
- `saved_tokens`: tokens avoided thanks to trimming or caching

#### Rule

Dashboards and aggregated `used` metrics must be derived from:

- `billable_input_tokens + billable_output_tokens`

and **never** from generic observed fields alone.

#### Why

This separates:

- “the tool looked at these tokens”
from
- “these tokens should count as effective consumption”.

That distinction is the core missing concept today.

### P2. Event Type Taxonomy

Add an explicit event classification field such as:

- `count`
- `trim`
- `cache`
- `rag_search`
- `analysis`
- `orchestration`

and optionally an `accounting_mode` field:

- `observational`
- `billable`
- `derived`

#### Example

- `count_tokens_tool` → observational
- `count_messages_tokens_tool` → observational
- `optimize_messages` → derived with savings
- `cache_context` → derived with savings and partial billable reuse model
- `search_context` → observational unless future policy says otherwise
- `analyze_context_health_tool` → observational
- `get_orchestration_advice` → observational

This gives aggregation logic enough context to scale safely as new tools appear.

### P3. Budget Policy Tiers

Replace the implicit “some tools consume budget” behavior with an explicit policy.

#### Tier A — Local Computational Budget

Tracks local context-processing load.

Includes tools that inspect, trim, search, or transform tokenized payloads.

#### Tier B — Prompt-Facing Effective Budget

Tracks the amount of token payload that would matter for downstream model context usage.

This is the budget that most product-facing dashboards should prioritize.

#### Decision

Context-Life should support both tiers, but the UI must label them clearly:

- `runtime_processed`
- `effective_prompt_used`
- `effective_saved`

This avoids forcing one overloaded “budget” number to mean everything.

### P4. Fix Aggregation Contract

Update weekly and all-time aggregation in `mmcp/session_store.py` to compute totals from canonical billable fields rather than `input_tokens + output_tokens`.

#### Required contract

- `used` = `SUM(billable_input_tokens + billable_output_tokens)`
- `saved` = `SUM(saved_tokens)`
- keep observed totals available separately for diagnostics

#### Immediate effect

This removes the current `cache_context` double-count risk and makes totals comparable across heterogeneous tool types.

### P5. Tool-Specific Instrumentation Rules

Define per-tool accounting semantics.

#### `count_tokens_tool`

- observational only
- should not inflate model usage by default

#### `count_messages_tokens_tool`

- observational only
- useful for diagnostics and capacity planning

#### `optimize_messages`

- observed input = original message tokens
- observed output = trimmed message tokens
- billable usage = trimmed message tokens when reporting effective prompt payload
- saved tokens = original minus trimmed

#### `cache_context`

- observed input = full payload before provider cache reuse
- observed output = processed payload representation if needed
- billable usage must represent only the portion that remains effectively uncached under the selected policy
- saved tokens = cached reusable prefix amount
- never mirror `total_tokens` into both billable input and output unless there is a true semantic reason

#### `search_context`

- observed input = query + selected chunk payload if measured
- billable usage = zero by default unless the retrieved context is promoted into prompt-facing accounting

#### `analyze_context_health_tool` and `get_orchestration_advice`

- observational by default
- should not distort model usage dashboards

### P6. End-to-End Telemetry Benchmark Suite

Extend `benchmarks/run_context_benchmarks.py` with accounting validation scenarios.

#### New benchmark coverage

1. **Per-tool event generation**
   - verify that each instrumented tool emits the expected accounting fields

2. **Aggregation correctness**
   - verify weekly totals from synthetic fixtures with mixed event types

3. **Double-count regression test**
   - verify `cache_context` contributes only the intended effective usage

4. **Budget policy correctness**
   - verify Local Computational Budget vs Prompt-Facing Effective Budget stay internally consistent

5. **Dashboard contract verification**
   - verify CLI/TUI summaries match canonical aggregation output

### P7. Scalable Storage Evolution

Extend the SQLite schema without breaking the current product experience.

#### Suggested additions to `usage_events`

- `event_type`
- `accounting_mode`
- `observed_input_tokens`
- `observed_output_tokens`
- `billable_input_tokens`
- `billable_output_tokens`
- `saved_tokens`
- `budget_scope`

#### Compatibility strategy

- keep legacy fields temporarily,
- backfill new fields from old data where safe,
- migrate aggregations and UI to the new canonical fields,
- deprecate legacy totals only after the benchmark suite passes.

## 8. Implementation Plan

### Phase 1 — Semantics First

1. Define canonical field meanings in code and docs.
2. Introduce new telemetry schema and migration strategy.
3. Update telemetry extraction in `mmcp/telemetry_service.py`.
4. Mark observational vs billable behavior per tool.

### Phase 2 — Aggregation Integrity

1. Update `mmcp/session_store.py` aggregation queries.
2. Split observed totals from effective totals.
3. Correct the `cache_context` usage model.
4. keep backwards-compatible adapters for current UI calls if needed.

### Phase 3 — Budget Expansion

1. Define budget scopes and labels in `mmcp/token_counter.py` and server responses.
2. Decide which tools affect runtime budget, effective budget, or both.
3. Expose both metrics in `status://token_budget` and telemetry summaries.

### Phase 4 — Verification and Benchmarking

1. Add unit tests for tool-specific accounting.
2. Add integration tests for persistence and weekly aggregation.
3. Extend benchmark script with telemetry/accounting validation.
4. Verify TUI/CLI output against canonical fixtures.

### Phase 5 — Product Hardening

1. Update dashboard labels to reflect the new semantics.
2. Document what `used`, `saved`, `runtime_processed`, and `effective_prompt_used` mean.
3. Promote the new accounting as the default only after benchmark and regression gates pass.

## 9. Success Criteria

This RFC is successful only if all of the following are true:

1. No aggregation path uses ambiguous `input + output` totals for final product metrics.
2. `cache_context` no longer double counts usage in weekly per-model totals.
3. Every instrumented tool has a documented accounting mode.
4. Dashboard `used` numbers map to canonical billable semantics.
5. Budget endpoints clearly distinguish runtime load vs effective prompt usage.
6. Benchmark suite includes at least one end-to-end telemetry correctness scenario.
7. CLI/TUI output remains understandable and stable after schema evolution.

## 10. Risks and Tradeoffs

### Risk 1 — More schema complexity

Adding explicit accounting fields increases storage and implementation complexity.

**Why it is worth it:** the current ambiguity is already complexity, just hidden and dangerous.

### Risk 2 — Existing dashboards may change numerically

After semantics are corrected, totals shown to users may go down or shift.

**Why it is worth it:** lower but honest numbers are better than inflated numbers that drive bad decisions.

### Risk 3 — Backfill may be imperfect

Historical data collected under ambiguous semantics may not be fully recoverable.

**Mitigation:** keep legacy history clearly labeled as pre-canonical telemetry.

## 11. Alternatives Considered

### Alternative A — Minimal patch only for `cache_context`

Fix the duplicate assignment and keep the rest unchanged.

**Pros**:

- fastest patch,
- removes the most visible bug.

**Cons**:

- does not solve semantic ambiguity,
- future tools can reintroduce the same class of bug,
- budget remains partial.

### Alternative B — Keep one global overloaded `used` metric

Continue aggregating everything into a single number.

**Pros**:

- simpler UI.

**Cons**:

- conceptually wrong,
- hard to scale,
- impossible to explain rigorously.

### Decision

Choose the canonical multi-field accounting model because it is the only option that scales without lying.

## 12. Deliverables

- this RFC: `docs/RFC-003-telemetry-budget-integrity-and-scalability.md`
- updated telemetry semantics in `mmcp/telemetry_service.py`
- updated aggregation logic in `mmcp/session_store.py`
- updated budget exposure in `mmcp/token_counter.py` and `mmcp/server.py`
- benchmark coverage in `benchmarks/run_context_benchmarks.py`
- regression tests for accounting correctness

## 13. Recommendation

Implement in this order:

1. define canonical semantics,
2. fix `cache_context` accounting and aggregation queries,
3. separate observational vs billable metrics,
4. expand budget into explicit scopes,
5. add end-to-end telemetry benchmarks,
6. update CLI/TUI labels only after the accounting contract is stable.

## 14. Final Position

The benchmark and budget review shows something IMPORTANT: the project is **not broken** — it is **maturing**.

The optimization features already work. The next step is to make the numbers trustworthy enough that product, benchmarking, and future orchestration can all rely on them without semantic doubt.

That is the right next RFC because scalability is not only about speed. It is also about whether your metrics still mean the same thing when the system gets bigger.
