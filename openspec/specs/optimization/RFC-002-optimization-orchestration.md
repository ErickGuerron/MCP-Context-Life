# RFC-002: Optimization and Orchestration Advisor

**Status**: Proposed  
**Author**: Erick Guerron / Gemini CLI  
**Date**: 2026-03-28  
**Scope**: Performance, UX, and Intelligent Orchestration with Gentle AI

## 1. Summary
This RFC proposes a series of architectural improvements to Context-Life (CL) aimed at eliminating startup latency (Cold Start), optimizing token counting efficiency (Caching), and introducing a "Context Advisor" layer for proactive orchestration when running alongside Gentle AI.

## 2. Motivation
Benchmarks from `RFC-001` (Validation Phase) revealed:
- **RAG Cold Start**: ~12 seconds (unacceptable for a CLI tool).
- **Trimming Overhead**: ~14ms for 100 messages (potential bottleneck for large histories).
- **Orchestration Gap**: The MCP is reactive; it doesn't advise the LLM on context health.

## 3. Proposed Changes

### P1: Lazy Loading for RAG Engine
**Problem**: Embedding models are loaded into RAM during class instantiation, regardless of whether RAG tools are called.
**Solution**: Defer model loading until the first `index_*` or `search` operation is performed.
**Technical Detail**:
- Move `_get_embedding_function()` call to a cached property or a lazy-init getter.
- Impact: Reduces MCP startup time from 12s to <50ms.

### P2: Token Count Caching (LRU)
**Problem**: The `smart` trimming strategy repeatedly calls `tiktoken` for the same message fragments during its iterative priority ladder.
**Solution**: Implement an LRU (Least Recently Used) cache for token counts indexed by the SHA-256 hash of the content string.
**Technical Detail**:
- Use `functools.lru_cache` on a internal helper or a dictionary in `TokenBudget`.
- Avoid caching small strings (< 10 chars) to prevent overhead.

### P3: Environment & Orchestrator Detection
**Problem**: The MCP treats all clients equally, missing optimization opportunities for Gentle AI.
**Solution**: Implement an auto-detection layer that checks for:
- Environment variables (e.g., `GENTLE_AI_ACTIVE`).
- Workspace artifacts (e.g., `.gemini/`, `ENGRAM` presence).
**Feature**: If detected, enable "Advisor Mode" in metadata responses.

### P4: New Tool: `analyze_context_health`
**Description**: A diagnostic tool that provides a "Health Score" for the current context window.
**Input**: `messages: list[dict]`, `max_tokens: int`.
**Output JSON Structure**:
```json
{
  "health_score": 0-100,
  "metrics": {
    "redundancy_ratio": "float",
    "system_to_user_ratio": "float",
    "noise_estimate": "low|med|high"
  },
  "recommendations": ["list of strings"],
  "orchestrator_hints": {
    "should_trim_now": "boolean",
    "suggested_strategy": "smart|digest|summary"
  }
}
```

## 4. Implementation Plan

### Phase 1: Core Optimization (The "Speed" Phase)
1. Refactor `mmcp/rag_engine.py` to use a lazy model loader.
2. Update `mmcp/token_counter.py` with an LRU cache for `count_tokens`.
3. Re-run `tests/test_performance_and_verification.py` to confirm startup < 1s.

### Phase 2: Intelligence Layer (The "Advisor" Phase)
1. Implement `mmcp/orchestrator_detector.py`.
2. Create the `analyze_context_health` logic in `mmcp/trim_history.py` (since it shares the logic for analyzing message importance).
3. Expose the new tool in `mmcp/server.py`.

### Phase 3: Gentle AI Integration
1. Update `mmcp/cache_manager.py` to include "Advisor Hints" in the cache metadata if an orchestrator is detected.

## 5. Security and Safety
- **Privacy**: The SHA-256 hashes for the token cache never leave the local machine.
- **Resource Limits**: The LRU cache will have a fixed size (e.g., 1024 entries) to avoid memory leaks.

## 6. Verification
- **Unit Tests**: Ensure `analyze_context_health` returns consistent scores.
- **Benchmarks**: Compare `trim_messages` latency before and after token caching.
- **Integration**: Verify that `RAGEngine` doesn't load the model until `search` is called.

---
**Approval Signature**: Erick Guerron (Owner) / Gemini CLI (Architect)
