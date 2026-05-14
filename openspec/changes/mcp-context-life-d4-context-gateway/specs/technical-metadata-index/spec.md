# Delta for technical-metadata-index

## Purpose

Index technical metadata that enables context recovery and budget decisions. Metadata must be independent of Engram and complement (not compete with) Engram's global memory.

## ADDED Requirements

### Requirement: Technical Metadata Schema

When indexing content, the system SHALL store technical metadata:

```json
{
  "type": "code|architecture|decision|bugfix|pattern",
  "project": "current_project_name",
  "topic_key": "architecture/auth-model",
  "session_id": "abc123",
  "file_hash": "sha256_of_source_file",
  "chunk_index": 5,
  "task_state": "pending|in_progress|completed",
  "token_cost": 1500,
  "summary_objective": "user goal at indexing time"
}
```

#### Scenario: Code file indexed with metadata

- GIVEN a Python file is indexed
- WHEN `index_knowledge` is called
- THEN metadata includes `type: "code"`, `file_hash`, `chunk_index`
- AND `task_state: "in_progress"` if file is being modified

### Requirement: Pre-Filter Before Vector Search

Search operations MUST apply metadata filters BEFORE vector search:

1. Filter by `type` if specified
2. Filter by `project` if specified
3. Filter by `session_id` if specified
4. THEN perform vector search on filtered subset

#### Scenario: Filter before search

- GIVEN 1000 chunks indexed
- WHEN `search_context` is called with `type: "code"`
- THEN only chunks with `type: "code"` are searched
- AND search is faster due to reduced candidate set

### Requirement: Engram Complement Mode

When Engram is active and has results, Context-Life SHOULD still index and serve technical metadata (code, file_hash, task_state) that Engram does not index.

#### Scenario: Engram active, context-life still serves

- GIVEN Engram is active and returned results
- WHEN orchestrator calls `search_context` with technical query (file paths, code)
- THEN Context-Life RAG returns code-specific results
- AND no conflict with Engram

## Edge Cases

### Requirement: Metadata-Only Search

If query is purely metadata-driven (e.g., "show me task states"), return results without vector embedding search.

#### Scenario: Metadata-only query

- GIVEN user asks "what tasks are in progress"
- WHEN `search_context` is called with `task_state: "in_progress"`
- THEN results are returned from metadata index only
- AND no vector search is performed