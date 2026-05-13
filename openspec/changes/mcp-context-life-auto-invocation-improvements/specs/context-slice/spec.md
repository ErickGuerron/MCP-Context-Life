# Delta for context-slice

Extends `openspec/specs/mcp-status-display/spec.md` and related context optimization specs.

## ADDED Requirements

### Requirement: Cache-Optimized Context Slice

The system SHALL support `ContextSlice` objects that include cache metadata for auto-invoke optimization.

A `ContextSlice` MUST carry:

- `cache_key`: SHA-256 hash of the operation signature
- `cache_hit`: boolean indicating if this was a cache hit
- `ttl_seconds`: remaining TTL if cached
- `latency_ms`: execution time

#### Scenario: Context slice carries cache metadata

- GIVEN an auto-invoke operation returns a result
- WHEN the result is wrapped in `ContextSlice`
- THEN the slice includes `cache_key`, `cache_hit`, `ttl_seconds`, `latency_ms`

### Requirement: Lazy Module Loading

The cache layer SHALL support lazy loading of heavy modules (e.g., embeddings, RAG components) to reduce startup time.

#### Scenario: Heavy module loaded on first cache miss

- GIVEN a cache miss occurs and the operation requires heavy modules
- WHEN the first invocation executes
- THEN heavy modules are loaded lazily
- AND subsequent cache hits bypass module loading entirely

## MODIFIED Requirements

### Requirement: Auto-Invoke Context Optimization

(Previously: Context slice returned without cache awareness)

When `cache_context` or `optimize_messages` is called in auto-invoke context, the response MUST include cache-aware fields:

- `cache_hit: bool`
- `tokens_saved: int`
- `latency_ms: int`

#### Scenario: Cache-aware context returned

- GIVEN `optimize_messages` is called with auto-invoke context
- WHEN the operation completes
- THEN the response includes `cache_hit`, `tokens_saved`, `latency_ms`
- AND these fields accurately reflect the cache state

## Edge Cases

### Requirement: Cache Key Generation for Complex Args

The system MUST handle complex nested arguments when generating cache keys. Nested objects and arrays MUST be canonicalized deterministically.

#### Scenario: Nested args produce stable key

- GIVEN an auto-invoke request with nested object args: `{"tools": [{"name": "a", "params": {"x": 1}}]}`
- WHEN the cache key is generated
- THEN the same args produce the same key regardless of dict ordering
- AND different nested structures produce different keys

### Requirement: Context Slice Fallback on Cache Failure

If cache lookup fails mid-operation (e.g., corrupted entry), the system MUST fall back to normal execution.

#### Scenario: Corrupted cache entry falls back

- GIVEN a cache entry exists but is corrupted (e.g., unpickling fails)
- WHEN cache lookup is attempted
- THEN the operation executes normally (cache miss behavior)
- AND the corrupted entry is invalidated