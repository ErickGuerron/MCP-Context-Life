# RFC: Context-Life Session Cache and Usage TUI v1

## Status

- Proposed
- Date: 2026-03-28
- Author: OpenCode

## Objective

Turn Context-Life into a session-visible optimization layer that:

- makes token savings observable from the start of real user workflows,
- persists optimization context across local sessions when safe,
- exposes a TUI where users can inspect remaining budget and consumption by agent, client, provider, and model,
- normalizes telemetry across OpenCode, Claude Code, Codex, and other MCP-compatible hosts,
- keeps the current local-first and provider-agnostic philosophy unless vendor-specific optimizations are explicitly enabled.

## Background

This RFC is driven by the latest validation run requested after the recent MCP changes.

Files reviewed:

- `benchmarks/run_context_benchmarks.py`
- `benchmarks/context_benchmark_results.json`
- `mmcp/cache_manager.py`
- `mmcp/server.py`
- `README.md`

Latest commands executed:

- `python -m pytest`
- `python benchmarks/run_context_benchmarks.py`

Observed state:

- `pytest` collected `0` tests, so the project currently relies on benchmarks and manual validation rather than automated regression coverage.
- The benchmark generated at `2026-03-28 16:23:03` confirms the trim fix is real.
- The cache loop still only shows savings after repeated calls inside the same process.

## Current Benchmark Snapshot

Source: `benchmarks/context_benchmark_results.json`

- total benchmark runtime: `14611.008 ms`
- RAG indexing time: `2771.362 ms`
- indexed files: `9`
- indexed chunks: `203`

### 1. Trim History

Realistic conversation baseline:

- original size: `3203` tokens

Representative results:

| Strategy | Budget | Output Tokens | Saved Tokens | Within Budget | Elapsed ms |
|---|---:|---:|---:|---|---:|
| tail | 800 | 621 | 2582 | yes | 1.847 |
| head | 800 | 591 | 2612 | yes | 1.734 |
| smart | 800 | 744 | 2459 | yes | 4.514 |
| tail | 1200 | 1074 | 2129 | yes | 2.570 |
| head | 1200 | 1176 | 2027 | yes | 2.136 |
| smart | 1200 | 1194 | 2009 | yes | 4.302 |

Overflow case:

- original size: `3040` tokens
- declared budget: `500` tokens
- actual `smart` output: `65` tokens
- saved tokens: `2975`
- budget respected: `yes`

Interpretation:

- the trim correction is materially successful,
- the core budget guarantee now holds in the benchmarked overflow path.

### 2. Cache Loop

Stable-prefix run:

- hits across 3 identical calls: `[false, true, true]`
- static prefix size: `804` tokens
- full payload size: `2405` tokens
- tokens saved after 3 calls: `1608`

Partial RAG change:

- full cache hit: `no`
- static prefix size after change: `808` tokens
- stable base prefix estimate: `383` tokens

Interpretation:

- repeated calls inside one live process benefit from the current design,
- the first call of a fresh session still pays full cost,
- base prompt reuse is only partially represented in metadata and is not persisted across sessions.

### 3. RAG Retrieval

Observed behavior:

- query latency stays between `18.768 ms` and `33.657 ms`
- indexing completes without errors
- retrieval remains budget-aware and operational

Interpretation:

- RAG is no longer the primary blocker,
- observability and session continuity are now the bigger product gap.

## Problem Statement

Context-Life optimizes payload shape, but it does not yet optimize the user experience of cost visibility.

Today:

1. `cache_context` in `mmcp/server.py` prepares messages for cache-friendly ordering.
2. `_cache_loop = CacheLoop()` lives only in memory for the current process.
3. `cache_context` returns metadata such as `is_cache_hit`, `base_prefix_hash`, and `tokens_saved`.
4. No durable session state is restored on restart.
5. No unified dashboard shows how much budget remains per client, model, agent, or provider.

Consequence:

- users cannot feel the benefit immediately in a new session,
- users cannot inspect where tokens are going across tools,
- users cannot compare Codex vs Claude Code vs OpenCode usage from one place,
- the MCP provides optimization signals but not full operational telemetry.

## Root Cause Analysis

### 1. Process-Local Cache Only

Current behavior in `mmcp/server.py` and `mmcp/cache_manager.py`:

- cache state is stored in memory only,
- the cache loop remembers only the last seen prefixes in the current process,
- restarting the MCP server resets learned cache state.

Consequence:

- the first request after restart behaves like a cold start even if the same user, workspace, and instructions were used minutes earlier.

### 2. Provider Cache Is Not Materialized

Current behavior:

- Context-Life calculates hashes and token estimates,
- but it does not emit provider-specific cache directives or consume provider-side cache APIs.

Consequence:

- “cacheable” does not always become “actually discounted” at runtime,
- token savings remain advisory unless the host/provider honors compatible cache semantics.

### 3. Missing Usage Ledger

Current behavior:

- token budget tracking is in-process and coarse,
- there is no durable ledger of events by host, agent, provider, or model,
- there is no normalized schema for telemetry coming from heterogeneous clients.

Consequence:

- users cannot answer basic operational questions such as:
  - how much budget remains today for Claude Sonnet in Claude Code,
  - which OpenCode agent spent the most tokens this session,
  - whether Codex consumed more prompt tokens than Claude for the same repository.

### 4. No Operator Surface

Current behavior:

- the MCP exposes tools and resources,
- but there is no TUI for live inspection, filtering, alerts, or drill-down.

Consequence:

- the product is technically useful but operationally invisible.

## Goals

- persist safe cache state and session telemetry across MCP restarts,
- make savings visible from the beginning of practical user workflows,
- provide a local TUI for usage inspection across clients, agents, providers, and models,
- define a normalized telemetry contract for MCP hosts,
- preserve privacy and local-first execution by default,
- support graceful degradation when a host cannot expose full usage data.

## Non-Goals

- guaranteeing provider billing accuracy when the provider does not expose auditable counters,
- replacing provider-native dashboards,
- introducing a hosted SaaS dependency,
- forcing all MCP clients to implement the same metadata schema on day one,
- claiming first-call provider-side cache savings where the provider API fundamentally cannot deliver them.

## Proposal

### 1. Introduce a Persistent Session Cache Layer

Add a new persistence component, for example `mmcp/session_store.py`, responsible for storing:

- base prefix hashes,
- optional canonical prefix payloads,
- last-seen workspace fingerprint,
- host/client identifier,
- provider/model identifier when available,
- timestamp, TTL, and reuse counters.

Suggested storage:

- SQLite for structured metadata,
- optional compressed JSON blobs for canonical prefix payload snapshots,
- default local path under the existing data directory.

Required behavior:

1. On server startup, restore recent reusable prefix entries.
2. On each `cache_context` call, check both in-memory and persisted cache state.
3. Promote persisted matches back into hot memory.
4. Expire entries by TTL and size budget.
5. Never persist sensitive payloads unless the user explicitly allows payload retention.

Privacy-safe default:

- persist hashes and aggregate metrics only,
- allow full-prefix persistence behind an explicit config flag.

### 2. Add Session Prewarm Semantics

The honest way to make savings visible early is not to lie about the first call. It is to prewarm intentionally.

Add a prewarm flow:

1. client sends stable system/developer context at session start,
2. Context-Life stores the normalized base prefix,
3. if provider adapters are enabled, emit cache-ready directives for the target provider,
4. mark the session as warmed for later turns.

New MCP surface:

- `prewarm_session(messages, host, agent, provider, model, workspace_id)`
- `session_status(session_id)`

Expected outcome:

- first conversational turn after prewarm can reuse prepared state,
- users experience savings earlier in the session lifecycle,
- the product remains explicit about cold-start vs warm-start behavior.

### 3. Add Provider-Aware Cache Adapters

Create an adapter layer, for example `mmcp/provider_adapters.py`, with optional integrations for:

- Anthropic prompt caching,
- OpenAI cache-compatible metadata when available,
- Google/Gemini cache semantics,
- a no-op fallback for unknown providers.

Design rule:

- core MCP behavior stays provider-agnostic,
- provider-specific optimizations are additive and feature-flagged.

This is the only path that can convert “cacheable prefix” into “real provider-side discounted prefix” when the upstream platform supports it.

### 4. Create a Normalized Usage Event Schema

Define one internal event model for all telemetry.

Suggested fields:

- `timestamp`
- `session_id`
- `workspace_id`
- `host_name` (`opencode`, `claude-code`, `codex-cli`, etc.)
- `agent_name`
- `provider_name`
- `model_name`
- `input_tokens`
- `output_tokens`
- `cached_input_tokens`
- `uncached_input_tokens`
- `effective_saved_tokens`
- `tool_name`
- `latency_ms`
- `metadata_source` (`reported`, `estimated`, `derived`)

Design rule:

- reported values beat estimated values,
- every field must carry provenance when the source is not authoritative.

### 5. Build a Usage Ingestion Path for Hosts

Add a new MCP tool such as:

- `record_usage_event(event_json)`

And support lightweight host-side adapters:

- OpenCode adapter reads agent/model/tool usage when available,
- Claude Code adapter maps its session/model counters into the normalized schema,
- Codex adapter maps model usage and request metadata,
- other hosts can submit partial events.

Graceful degradation:

- if a host only knows `model_name` and `input_tokens`, store partial usage,
- if a host knows no usage at all, Context-Life can still estimate prompt-side input tokens for its own tools.

### 6. Add a Local TUI for Usage and Remaining Budget

Introduce a terminal UI command, for example:

- `context-life usage`

Suggested screens:

1. Overview
   - total tokens today
   - total saved tokens
   - cache hit rate
   - active sessions

2. By Host
   - OpenCode
   - Claude Code
   - Codex
   - other MCP clients

3. By Agent
   - per-agent token consumption
   - remaining budget if a budget policy exists
   - hottest sessions

4. By Provider / Model
   - model-level breakdown
   - cached vs uncached input
   - estimated cost bands when pricing metadata is configured

5. Session Inspector
   - last requests
   - cache warm/cold state
   - top tools used
   - prefix reuse timeline

6. Alerts
   - near-budget thresholds
   - runaway agents
   - low cache-hit sessions

TUI implementation guidance:

- use `textual` or `rich` + live panels,
- default to read-only local inspection,
- refresh from the SQLite ledger and in-memory runtime stats,
- support keyboard filters by host, agent, provider, model, and time window.

### 7. Add Budget Policy Configuration

Extend config so users can optionally define local soft budgets.

Examples:

- daily budget per host,
- session budget per agent,
- monthly budget per provider/model,
- warning thresholds at `70%`, `85%`, and `95%`.

Important rule:

- these are local operational policies,
- they are not billing truth unless tied to authoritative provider telemetry.

### 8. Expose New MCP Resources

Recommended new resources:

- `usage://overview`
- `usage://hosts`
- `usage://agents`
- `usage://models`
- `session://active`

These resources let hosts query summarized data even without the TUI.

## TUI Functional Requirements

The TUI must let the user answer all of these without leaving the terminal:

- how much usage remains for each configured agent,
- which model is consuming the most input tokens,
- how much of the last hour was cached vs uncached,
- whether OpenCode saved more tokens than Claude Code today,
- whether a Codex session is currently cold, warming, or warm,
- which sessions deserve prewarm because they reuse the same base prompt repeatedly.

## Data Model and Storage

Recommended tables:

1. `sessions`
   - session metadata, host, workspace, provider, model, started_at, last_seen_at, status
2. `prefix_cache_entries`
   - base hash, rag hash, payload policy, ttl, hit counters, warmed_at
3. `usage_events`
   - normalized token events with provenance
4. `budget_policies`
   - optional local limits and alert thresholds
5. `budget_snapshots`
   - periodic aggregates for fast TUI rendering

Retention policy:

- compact raw events after a configurable window,
- keep hourly/daily aggregates longer,
- keep no raw payload content unless explicitly enabled.

## Rollout Plan

### Phase 1: Telemetry Foundations

1. Add normalized usage schema.
2. Add `record_usage_event`.
3. Persist usage events locally.
4. Add MCP summary resources.

### Phase 2: Session Cache Persistence

1. Add durable prefix cache metadata.
2. Restore recent state on startup.
3. Add prewarm semantics and cold/warm session states.
4. Benchmark cold-start vs warmed-session reuse.

### Phase 3: TUI

1. Add `context-life usage` command.
2. Ship overview, host, agent, and model views.
3. Add threshold alerts and session inspector.

### Phase 4: Provider Adapters

1. Add feature-flagged Anthropic adapter.
2. Add OpenAI and Gemini adapters where technically possible.
3. Compare reported vs estimated savings in benchmarks.

## Success Criteria

This RFC is successful only if all items below are true:

- a fresh MCP process can restore recent cache metadata and session state safely,
- the system can distinguish cold, prewarmed, and warm sessions,
- users can inspect usage by host, agent, provider, and model from one TUI,
- the TUI shows remaining local budget for configured agents/models,
- telemetry clearly marks reported vs estimated values,
- benchmark suite includes cold-start and warm-start scenarios,
- provider-specific cache adapters remain optional and do not break the local-first baseline,
- no sensitive prompt payload is persisted by default.

## Risks and Tradeoffs

### Risk 1: False Precision

- different hosts expose different telemetry quality,
- mitigation: attach provenance to every metric and separate reported from estimated values.

### Risk 2: Privacy Regression

- persistent session state can become a data-retention risk,
- mitigation: hash-only default, TTL expiration, encrypted local storage as a future option.

### Risk 3: Adapter Fragility

- provider cache APIs and host metadata formats will evolve,
- mitigation: isolate integrations behind adapters and feature flags.

### Risk 4: TUI Scope Creep

- a dashboard can balloon into a second product,
- mitigation: start with usage visibility and budget alerts only.

### Risk 5: Misleading “Remaining Usage” Semantics

- not every provider has a real hard quota visible to the local tool,
- mitigation: model “remaining usage” as local policy by default and label it clearly unless authoritative quota data exists.

## Deliverables

- new RFC in `docs/rfc-session-cache-and-usage-tui-v1.md`
- telemetry schema and local ledger modules in `mmcp/`
- session persistence layer for cache metadata
- prewarm/session-status MCP tools
- usage summary resources
- TUI command for usage inspection
- benchmark extensions for cold vs warm sessions and telemetry validation
- README updates describing usage instrumentation and TUI flow

## Recommendation

Implement in this order:

1. normalize and persist usage events,
2. add prewarm and durable session cache metadata,
3. ship a minimal read-only TUI,
4. add local budget policies and alerts,
5. integrate provider-specific cache adapters only after telemetry is trustworthy.
