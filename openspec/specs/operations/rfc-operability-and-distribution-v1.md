# RFC: Context-Life Operability and Distribution v1

## Status

- Proposed
- Date: 2026-03-28
- Author: OpenCode

## Objective

Consolidate the latest benchmark analysis, runtime-flow findings, and distribution improvements into a single plan that:

- preserves response quality and agent behavior,
- fixes budget-compliance gaps in trimming,
- improves benchmark coverage and observability,
- gives users safe performance/resource configuration knobs,
- provides a more stable and customizable installation story,
- aligns self-upgrades with GitHub tags/releases instead of repository HEAD.

## Background

This RFC extends the optimization work documented in `docs/rfc-context-optimization-v2.md` using the latest benchmark run captured in `benchmarks/context_benchmark_results.json`.

Files reviewed for this RFC:

- `benchmarks/run_context_benchmarks.py`
- `benchmarks/context_benchmark_results.json`
- `mmcp/trim_history.py`
- `mmcp/rag_engine.py`
- `mmcp/cache_manager.py`
- `mmcp/server.py`
- `mmcp/cli.py`
- `pyproject.toml`
- `README.md`

## Latest Benchmark Snapshot

Source: `python benchmarks/run_context_benchmarks.py`

- generated at: `2026-03-28 14:40:04`
- total benchmark runtime: `13161.848 ms`
- RAG indexing time: `2421.728 ms`
- indexed files: `8`
- indexed chunks: `165`

### 1. Trim History

Realistic conversation baseline:

- original size: `3191` tokens

Measured results:

| Strategy | Budget | Output Tokens | Saved Tokens | Reduction | Within Budget | Elapsed ms |
|---|---:|---:|---:|---:|---|---:|
| tail | 800 | 608 | 2583 | 80.95% | yes | 1.853 |
| head | 800 | 625 | 2566 | 80.41% | yes | 1.771 |
| smart | 800 | 795 | 2396 | 75.09% | yes | 4.422 |
| tail | 1200 | 1038 | 2153 | 67.47% | yes | 2.273 |
| head | 1200 | 833 | 2358 | 73.90% | yes | 2.001 |
| smart | 1200 | 1161 | 2030 | 63.62% | yes | 4.243 |
| tail | 1600 | 1480 | 1711 | 53.62% | yes | 2.398 |
| head | 1600 | 1469 | 1722 | 53.96% | yes | 2.359 |
| smart | 1600 | 1480 | 1711 | 53.62% | yes | 3.550 |

Overflow case:

- original size: `3040` tokens
- declared budget: `500` tokens
- actual `smart` output: `1362` tokens
- saved tokens: `1678`
- budget respected: `no`

Interpretation:

- `smart` improved materially for realistic flows.
- The documented hard guarantee is still false for oversized-anchor scenarios.

### 2. Cache Loop

Stable-prefix run:

- hits across 3 identical calls: `[false, true, true]`
- static prefix size: `819` tokens
- full payload size: `2392` tokens
- tokens saved after 3 calls: `1638`

Partial RAG change:

- cache hit: `no`
- static prefix size after change: `823` tokens
- stable base prefix estimate: `400` tokens

Interpretation:

- Stable cache behavior is healthy.
- A small RAG change still invalidates the full static prefix, including the unchanged base instructions.

### 3. RAG Retrieval

Observed behavior:

- `engine.search(...)` now returns real results: `5`, `5`, and `4` depending on query.
- query latency stays between `19.486 ms` and `33.303 ms`.
- indexing finishes without errors.

Representative retrieval behavior:

| Query | Budget | Current Results | Current Tokens | Skip Candidate Results | Skip Candidate Tokens |
|---|---:|---:|---:|---:|---:|
| cache prefix hashing rag context prompt caching | 350 | 3 | 237 | 4 | 303 |
| smart trimming protected messages token budget | 500 | 5 | 489 | 5 | 489 |
| semantic search token budget chunk selection | 500 | 4 | 415 | 4 | 415 |

Interpretation:

- The new RAG flow is healthier than the prior benchmark baseline.
- Skip-and-continue remains the correct packing policy under tight budgets.

## Current Findings

### A. What Improved

1. `smart` trim now stays inside budget for realistic scenarios at `800`, `1200`, and `1600` tokens.
2. Cache-loop behavior remains stable and still produces repeatable cache hits on identical prefixes.
3. `RAGEngine.search()` now returns non-zero results, which means the current benchmark reflects real retrieval rather than a broken execution path.
4. End-to-end benchmark runtime remains reasonable for local CPU execution.

### B. What Is Still Broken

1. `mmcp/trim_history.py` still fails its own contract for overflow cases where the protected `system` and `developer` anchors alone exceed the budget.
2. The cache layer hashes the whole static prefix as one block, so a small RAG delta destroys reuse of the unchanged base prompt.
3. Installation and upgrade UX are still too rigid for real users.
4. Runtime tuning is effectively hardcoded; users cannot safely customize storage and performance behavior without touching code.

## Root Cause Analysis

### 1. Smart Trim Overflow Failure

Documented guarantee in `mmcp/trim_history.py`:

- phase 5 says: trim system messages to fit
- phase 6 says: guarantee output token count `<= max_tokens`

Actual behavior:

- the enforcement loop only drops `kept_middle` or `summary_injection`
- if `system_msgs + recent_msgs` still exceed budget, the function returns an oversized payload

Consequence:

- downstream clients can still receive an over-budget context even when the API promises strict compliance

### 2. Cache Prefix Coarseness

Current behavior in `mmcp/cache_manager.py`:

- all static messages are serialized into one hashed block
- RAG injection is appended into the same static payload

Consequence:

- base instructions cannot stay cacheable when only the RAG section changes

### 3. Distribution and Upgrade Instability

Current behavior in `mmcp/cli.py`:

- `context-life upgrade` runs `pip install --upgrade git+https://...`
- this tracks repository HEAD, not a tagged release

Consequence:

- upgrades are not tied to a stable released version
- users cannot easily pin, dry-run, or request a specific target version

### 4. Missing Runtime Configuration Layer

Current behavior:

- defaults for storage paths, retrieval thresholds, chunking, and token-budget behavior are embedded in code

Consequence:

- users cannot tune local resource usage safely
- customization pressure pushes people toward ad hoc code edits

## Goals

- guarantee strict token-budget compliance in every trim path
- expand benchmark coverage to catch regressions earlier
- expose safe runtime knobs that do not change semantic tool behavior
- support customizable installation profiles
- upgrade only to tagged GitHub releases by default

## Non-Goals

- changing answer semantics for MCP tools
- introducing hosted services or external paid APIs
- replacing the current local-first architecture
- adding configuration options that mutate deterministic outputs by default

## Proposal

### 1. Fix Smart Trim for Oversized Anchors

Introduce a final deterministic fallback when `system` and `developer` anchors alone exceed the budget.

Required behavior:

1. Preserve full anchors only when they fit.
2. If they do not fit, compact them into a bounded policy digest.
3. Keep the most recent user and assistant turns only if budget remains.
4. Return a payload that always satisfies `trimmed_token_count <= max_tokens`.

Suggested digest structure:

- system directives summary
- developer constraints summary
- non-negotiable execution rules
- last-known task objective

Acceptance criteria:

- overflow benchmark at `500` tokens returns `<= 500`
- no trim path violates declared budget
- deterministic output remains stable for identical inputs

### 2. Expand Benchmark Coverage

Add benchmark scenarios that reflect the real operational risks.

New benchmark groups:

1. oversized `system`/`developer` anchors only
2. cold-start vs warm-start RAG indexing and query latency
3. cache reuse with base prompt stable and RAG block changing
4. retrieval diversity and score quality under budgets
5. config-driven runs to prove resource tuning does not alter semantic outputs

New metrics to track:

- budget-compliance rate
- unique sources per retrieval
- score spread and average score
- cold vs warm elapsed time
- identical-input output diff checks

### 3. Segment Cache Prefixes

Split cache metadata into:

- `base_prefix_hash`: stable system/developer instructions
- `rag_prefix_hash`: injected knowledge block

Expected outcome:

- unchanged base instructions remain cacheable even when RAG changes
- cache telemetry becomes more informative

Acceptance criteria:

- partial-RAG-change scenario preserves reuse for the base prefix
- stable-prefix hit rate is no worse than current behavior

### 4. Add a Runtime Configuration Layer

Create a small config module that loads from:

1. built-in defaults
2. optional config file
3. environment-variable overrides

Suggested config file:

- `~/.config/context-life/config.toml`

Suggested safe knobs:

- RAG database path
- table name
- default `top_k`
- default `min_score`
- default `max_chunks_per_source`
- chunk size and overlap
- token budget defaults
- safety buffer
- local cache paths and size limits

Important rule:

- these knobs tune performance, storage, and local resource usage
- they must not silently alter the semantic contract of tool outputs beyond the explicitly chosen runtime parameters

### 5. Introduce Installation Profiles

Update `pyproject.toml` and `README.md` to support multiple installation paths.

Recommended profiles:

- `core`: token counting and trim features only
- `rag`: local retrieval stack
- `dev`: tests and linting
- `all`: full install

Recommended user-facing install modes:

- `pipx install context-life` for isolated CLI usage
- `pip install context-life[rag]` for local RAG-enabled installs
- `pip install -e ".[dev]"` for contributor workflow
- pinned installs by version for reproducible environments

### 6. Upgrade by GitHub Tag/Release, Not HEAD

Replace the current self-update path with release-aware behavior.

Required behavior:

1. `context-life upgrade` resolves the latest stable GitHub release/tag.
2. `context-life upgrade --version <tag>` installs a specific tagged version.
3. `context-life upgrade --dry-run` reports the target version without installing.
4. Default upgrade path never tracks arbitrary repository HEAD.

Implementation guidance:

- use GitHub release/tag metadata
- compare installed version with target version before install
- install from the tagged release artifact or versioned package source

### 7. Add a Diagnostic Command

Add `context-life doctor` for local environment validation.

Checks should include:

- Python version
- installed package version
- dependency presence
- config file path resolution
- LanceDB path access
- model cache availability
- upgrade channel visibility

This reduces support friction without changing runtime semantics.

## Rollout Plan

### Phase 1: Correctness First

1. Fix `smart` trim overflow behavior.
2. Add regression tests for oversized-anchor scenarios.
3. Extend benchmarks for strict budget compliance.

### Phase 2: Observability and Runtime Safety

1. Add config loading.
2. Add benchmark scenarios proving semantic stability under config changes.
3. Add `doctor` diagnostics.

### Phase 3: Distribution and Upgrade UX

1. Add installation profiles in `pyproject.toml`.
2. Update `README.md` for pip, pipx, editable, and pinned installs.
3. Replace HEAD-based upgrades with tag/release-aware upgrades.

### Phase 4: Cache Evolution

1. Split cache prefixes into base and RAG segments.
2. Benchmark partial-RAG-change cache reuse.
3. Promote segmented cache only if hit-rate and latency stay within target thresholds.

## Success Criteria

This RFC is successful only if all items below are true:

- overflow trim case at `500` tokens returns `<= 500`
- realistic `smart` trim cases remain within budget
- benchmark suite covers cold/warm and oversized-anchor scenarios
- config changes can tune local performance without breaking tool contracts
- installation docs support isolated, minimal, RAG, and dev workflows
- `context-life upgrade` follows GitHub tags/releases by default
- `context-life upgrade --version <tag>` works for explicit pinning
- segmented cache preserves base-prefix reuse when only RAG changes

## Risks and Tradeoffs

### Risk 1: Over-Compression of Anchors

- compacting `system`/`developer` anchors too aggressively can remove critical constraints
- mitigation: use deterministic digests with explicit priority ordering and regression fixtures

### Risk 2: Config Drift

- too many knobs can create hard-to-support local variants
- mitigation: keep a minimal config surface and document defaults clearly

### Risk 3: Release API Dependence

- GitHub API lookups can fail or be rate-limited
- mitigation: graceful fallback, caching, and explicit version install path

### Risk 4: Packaging Complexity

- extras and profile docs add maintenance overhead
- mitigation: keep profiles few and purposeful

## Deliverables

- benchmark updates in `benchmarks/run_context_benchmarks.py`
- latest captured results in `benchmarks/context_benchmark_results.json`
- trim overflow fix in `mmcp/trim_history.py`
- config layer in a new module such as `mmcp/config.py`
- release-aware upgrade flow in `mmcp/cli.py`
- installation updates in `pyproject.toml` and `README.md`
- this RFC in `docs/rfc-operability-and-distribution-v1.md`

## Recommendation

Implement in this order:

1. fix trim overflow correctness,
2. add regression benchmarks and tests,
3. introduce runtime config,
4. ship installation profiles,
5. replace HEAD-based upgrades with release-aware upgrades,
6. evolve cache segmentation after correctness and packaging are stable.
