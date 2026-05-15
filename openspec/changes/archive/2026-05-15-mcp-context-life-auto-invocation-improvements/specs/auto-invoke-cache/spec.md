# Delta for auto-invoke-cache

## ADDED Requirements

### Requirement: TTL-Based Cache with Key Deduplication

The system SHALL implement a TTL cache for auto-invoke results that avoids re-executing identical calls within a configurable time window.

The cache MUST use a deterministic hash of `(host, agent, provider, model, operation, args)` as the lookup key.

#### Scenario: Cache hit returns stored result

- GIVEN a previous auto-invoke completed with key `HASH_abc123`
- AND the TTL window has not expired
- WHEN an identical auto-invoke request arrives
- THEN the cached result is returned immediately
- AND no re-execution occurs

#### Scenario: Cache miss triggers execution

- GIVEN no prior auto-invoke matches the incoming request key
- WHEN the auto-invoke request arrives
- THEN the operation executes normally
- AND the result is stored in the cache with TTL

#### Scenario: TTL expiration forces re-execution

- GIVEN a cache entry exists but its TTL has expired
- WHEN an identical request arrives
- THEN the cache entry is invalidated
- AND the operation re-executes and updates the cache

### Requirement: Cache Key Hashing

The system MUST generate cache keys using SHA-256 over the canonical operation signature.

The signature MUST include: `host`, `agent`, `provider`, `model`, `operation_name`, and a normalized `args_json`.

#### Scenario: Identical requests produce same key

- GIVEN two auto-invoke requests with identical parameters
- WHEN their cache keys are computed
- THEN both produce the same SHA-256 hash

#### Scenario: Different args produce different key

- GIVEN two auto-invoke requests with different arguments
- WHEN their cache keys are computed
- THEN they produce different hashes

### Requirement: Deduplication of Concurrent Requests

The system MUST deduplicate concurrent requests for the same cache key, ensuring only one execution proceeds while others wait for the result.

#### Scenario: Concurrent duplicate requests

- GIVEN three concurrent auto-invoke requests with identical keys
- WHEN they arrive within the same event loop iteration
- THEN only one execution occurs
- AND all three requests receive the same result

### Requirement: Manual Cache Invalidation

The system SHALL expose a `cache_invalidate(key)` function that removes a specific entry, and a `cache_clear()` function that removes all entries.

#### Scenario: Manual invalidation removes entry

- GIVEN a cache entry exists for key `HASH_abc`
- WHEN `cache_invalidate(HASH_abc)` is called
- THEN the entry is removed
- AND subsequent requests for that key trigger fresh execution

#### Scenario: Clear removes all entries

- GIVEN cache contains multiple entries
- WHEN `cache_clear()` is called
- THEN all entries are removed

### Requirement: Configuration Flags

The cache layer MUST be controllable via config flags:

- `auto_invoke_cache.enabled: false` — deactivates the cache layer entirely

#### Scenario: Disabled cache bypasses lookup

- GIVEN `auto_invoke_cache.enabled` is `false`
- WHEN an auto-invoke request arrives
- THEN the cache is not consulted
- AND the operation executes directly without storing results

## Edge Cases

### Requirement: Cache Key Collision Resistance

The system MUST handle hash collisions gracefully. If two different operation signatures produce the same hash (improbable but possible), the cache SHALL store both with a unique entry identifier appended to the key.

#### Scenario: Hash collision handled

- GIVEN two different operation signatures produce identical SHA-256
- WHEN both are cached
- THEN both entries are stored separately
- AND retrieval uses both hash and entry metadata for disambiguation

### Requirement: Large Result Handling

The system SHALL limit cached result size to prevent memory exhaustion. Results exceeding `max_entry_size_bytes` (configurable, default 1MB) SHALL NOT be cached.

#### Scenario: Oversized result not cached

- GIVEN an auto-invoke result exceeds `max_entry_size_bytes`
- WHEN the cache store is attempted
- THEN the result is not stored
- AND the operation completes without caching
- AND a warning is logged