# RFC: MMCP Context Optimization v2

## Status

- Proposed
- Date: 2026-03-28
- Author: OpenCode

## Objective

Reduce MMCP context size more aggressively without degrading expected behavior:

- never exceed the declared token budget,
- preserve the highest-value context first,
- improve prompt-cache reuse when only part of the static prefix changes,
- keep RAG retrieval useful under tight token budgets,
- align telemetry with real chat-token accounting.

## Benchmark Basis

All numbers in this RFC come from `benchmarks/run_context_benchmarks.py` and the captured output in `benchmarks/context_benchmark_results.json`.

Benchmark corpus:

- indexed files: 7 Python files from `mmcp/`
- indexed chunks: 142
- total benchmark runtime: 13.55 s
- RAG indexing time: 2074.78 ms

## Current Baseline

### 1. Trim History

Realistic conversation baseline:

- original size: 2594 tokens

Measured results:

| Strategy | Budget | Output Tokens | Saved Tokens | Reduction | Within Budget |
|---|---:|---:|---:|---:|---|
| tail | 800 | 718 | 1876 | 72.32% | yes |
| head | 800 | 675 | 1919 | 73.98% | yes |
| smart | 800 | 1343 | 1251 | 48.23% | no |
| tail | 1200 | 1131 | 1463 | 56.40% | yes |
| head | 1200 | 1140 | 1454 | 56.05% | yes |
| smart | 1200 | 1343 | 1251 | 48.23% | no |
| tail | 1600 | 1540 | 1054 | 40.63% | yes |
| head | 1600 | 1575 | 1019 | 39.28% | yes |
| smart | 1600 | 1540 | 1054 | 40.63% | yes |

Overflow case:

- original size: 3041 tokens
- declared budget: 500 tokens
- actual `smart` output: 3041 tokens
- saved tokens: 0
- budget respected: no

### 2. Cache Loop

Stable-prefix run:

- hits across 3 identical calls: `[false, true, true]`
- static prefix size: 724 tokens
- full payload size: 1977 tokens
- tokens saved after 3 calls: 1448

Partial RAG change:

- cache hit: no
- static prefix size after change: 728 tokens
- stable base prefix estimate: 324 tokens

Interpretation: changing only the RAG block invalidates the full static prefix, including the 324-token stable base prompt.

### 3. RAG Retrieval

Observed behavior:

- direct `engine.search(...)` returned 0 results for all benchmark queries
- manual LanceDB query path returned usable candidates

This is a real execution failure, not a theoretical concern.

Measured retrieval opportunity under tight budget:

Query: `cache prefix hashing rag context prompt caching`

- budget 350, current break-on-overflow strategy: 3 results, 235 tokens
- budget 350, skip-and-continue candidate: 4 results, 301 tokens

That is:

- +1 result (`+33.3%` more retrieved chunks)
- still within the 350-token ceiling
- same source diversity, slightly worse average score but materially better recall

## Fields That Must Improve

### A. Budget Compliance

Problem:

- `trim_smart` does not guarantee `output <= max_tokens`.
- This breaks the core contract of the MCP and can overflow the downstream model context.

Evidence:

- realistic runs at 800 and 1200 fail budget compliance
- overflow benchmark misses the budget by 2541 tokens

Required outcome:

- 100% of trim outputs must respect the declared budget

### B. Value-Preserving Compression

Problem:

- current `smart` mode protects recent turns but can still keep too much high-cost context and remove too little low-value context.
- summary injection is effectively not contributing in practice.

Evidence:

- `smart` is less aggressive than `tail` and `head` at 800 and 1200
- output remains frozen at 1343 tokens for both 800 and 1200 budgets, which signals poor adaptation to tighter limits

Required outcome:

- trim strategy must adapt continuously as budgets shrink
- compressed memory must be cheaper than the messages it replaces

### C. Cache Segmentation

Problem:

- cache hashing treats the entire static prefix as one blob
- partial changes in RAG destroy cache reuse for unchanged base instructions

Evidence:

- stable base prompt is ~324 tokens
- changing only the RAG block forces a full cache miss on a ~728-token prefix

Required outcome:

- preserve cacheability for the stable base prompt even when RAG changes

### D. RAG Execution Robustness

Problem:

- current `engine.search()` depends on a pandas path and returns zero results in the benchmark environment
- retrieval under budget uses break-on-overflow, which can reduce recall unnecessarily

Evidence:

- `engine_results = 0` for all three benchmark queries
- skip-and-continue improved one benchmark case from 3 to 4 chunks within budget

Required outcome:

- `engine.search()` must return non-zero results when LanceDB has results
- budgeting logic should prefer filling the budget with smaller valid chunks over exiting early

### E. Metrics Consistency

Problem:

- cache token telemetry and chat token accounting use different counting methods

Impact:

- optimization decisions can be made on misleading numbers
- saved-token reports are harder to trust when comparing trim vs cache vs total prompt usage

Required outcome:

- one authoritative chat-token metric for all prompt-facing reports

## Proposed Changes

### 1. Strict Smart Trim Ladder

Replace the current protected-or-bust behavior with a strict ladder:

1. keep all system/developer messages only if they fit,
2. if not, compact system/developer into a bounded policy digest,
3. keep last user turn,
4. keep last assistant turn if budget allows,
5. keep additional recent turns by descending utility-per-token,
6. allocate a reserved summary budget for dropped history,
7. fill remaining budget with middle context only if it still fits.

Expected impact:

- fixes budget compliance failures
- should save an additional 143 to 668 tokens versus current `smart` behavior in the failing 800 and 1200 cases

### 2. Reserved Summary Budget

Instead of trying to summarize after greedy packing, reserve summary space upfront.

Suggested rule:

- reserve `min(120, max_tokens * 0.15)` tokens for historical digest when trimming is triggered

Digest format:

- user goal
- confirmed constraints
- decisions taken
- unresolved questions

Expected impact:

- makes the summary path actually executable
- retains semantic continuity at a predictable token cost

### 3. Two-Level Cache Hashing

Split static cache tracking into:

- `base_prefix_hash`: system + developer stable prompt
- `rag_prefix_hash`: injected knowledge block

Expected impact:

- preserves up to ~324 tokens of reusable base prefix in the measured partial-RAG-change scenario
- avoids turning every small retrieval delta into a full cache miss

### 4. RAG Search Without Pandas Hard Dependency

Replace `to_pandas()` in the retrieval path with `to_list()` or `to_arrow()`.

Expected impact:

- restores actual search results in environments without pandas
- removes a hidden runtime dependency from the critical path

### 5. Skip-And-Continue Budget Filling

When a candidate chunk does not fit, skip it and continue scanning later candidates.

Expected impact:

- better recall under tight budgets
- benchmark already shows improvement from 3 to 4 chunks at 350 tokens for one query

## Success Criteria

The RFC is considered successful only if all of these are true after implementation:

- trim budget compliance: 100%
- `smart` output at 800 tokens: `<= 800`
- `smart` output at 1200 tokens: `<= 1200`
- overflow case at 500 tokens: `<= 500`
- cache partial-RAG-change scenario keeps base-prefix reuse
- `engine.search()` returns the same non-zero order of magnitude as the direct LanceDB path
- RAG 350-token benchmark is never worse than current recall, and ideally matches the 4-result candidate path

## Mitigation Plan If Results Are Worse Than Expected

If the new approach reduces answer quality or retrieval precision, apply these safeguards in order:

### Mitigation 1: Adaptive Compression Thresholds

- do not activate summary compression for mild overflow
- only switch to digest mode after overflow exceeds a threshold such as 10% of budget

### Mitigation 2: Query-Class Policies

- conversational tasks: prioritize recent turns
- code/debug tasks: prioritize constraints, stack traces, and latest code references
- retrieval-heavy tasks: reserve more budget for RAG and less for dialogue history

### Mitigation 3: Score-Aware RAG Packing

- allow skip-and-continue only while score degradation stays within an acceptable band
- if lower-ranked chunks are too weak, keep the smaller result set

### Mitigation 4: Feature Flags

- ship `strict_smart_trim_v2`
- ship `segmented_cache_prefix`
- ship `rag_skip_fill`

This allows rollback per feature instead of reverting the entire optimization pass.

### Mitigation 5: Benchmark Gate

Do not promote the changes as default until benchmark deltas stay inside these limits:

- retrieval precision proxy degradation: <= 5%
- answer-quality regression in manual eval: none on critical workflows
- trim latency increase: <= 20%
- cache hit rate: equal or better on stable-prefix flows

## Deliverables

- benchmark script: `benchmarks/run_context_benchmarks.py`
- benchmark results: `benchmarks/context_benchmark_results.json`
- this RFC: `docs/rfc-context-optimization-v2.md`

## Recommendation

Implement in this order:

1. fix RAG runtime dependency and search path,
2. enforce strict budget compliance in `smart` trim,
3. add reserved digest budget,
4. split cache hashing into base and RAG segments,
5. rerun the same benchmark and compare deltas against this RFC baseline.
