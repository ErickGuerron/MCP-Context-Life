"""
Context-Life (CL) — LLM Context Optimization MCP Server

The main MCP server that exposes all context optimization tools:
  - count_tokens: Count tokens in text or message arrays
  - optimize_messages: Trim message history using tail/head/smart strategies
  - index_knowledge: Index files/directories into the local RAG
  - search_context: Semantic search over indexed knowledge
  - cache_context: Cache-aware message optimization
  - status://token_budget: Token budget resource
  - cache://status: Cache performance resource
"""

from __future__ import annotations

import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from mmcp.cache_manager import CacheLoop
from mmcp.orchestrator_detector import get_orchestrator_info
from mmcp.rag_engine import RAGEngine
from mmcp.token_counter import (
    DEFAULT_ENCODING,
    TokenBudget,
    count_messages_tokens,
    count_tokens,
    get_cache_info,
)
from mmcp.trim_history import analyze_context_health, trim_messages
from mmcp.telemetry_service import track_telemetry

# --- Server Instance ---
mcp = FastMCP(
    "Context-Life",
    instructions=(
        "Context-Life (CL) — LLM context optimization server. "
        "Use these tools to count tokens, trim message history, "
        "search indexed knowledge via RAG, and optimize context caching."
    ),
)

# --- Shared State (per-session singletons) ---
_token_budget = TokenBudget()
_rag_engine: Optional[RAGEngine] = None
_cache_loop = CacheLoop()


def _get_rag_engine() -> RAGEngine:
    """Lazy initialization of the RAG engine."""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine


# ============================================================
# TOOLS
# ============================================================


@mcp.tool()
@track_telemetry("count_tokens")
def count_tokens_tool(
    text: str,
    encoding: str = DEFAULT_ENCODING,
) -> str:
    """
    Count the number of tokens in a text string.

    Args:
        text: The text to count tokens for
        encoding: Tiktoken encoding (cl100k_base, o200k_base, p50k_base)

    Returns:
        JSON with token count and encoding used
    """
    token_count = count_tokens(text, encoding)
    _token_budget.consume(token_count)

    return json.dumps(
        {
            "token_count": token_count,
            "encoding": encoding,
            "budget": _token_budget.to_dict(),
        }
    )


@mcp.tool()
@track_telemetry("count_messages_tokens")
def count_messages_tokens_tool(
    messages: str,
    encoding: str = DEFAULT_ENCODING,
) -> str:
    """
    Count tokens for an OpenAI-style messages JSON array.

    Args:
        messages: JSON string of the messages array
                  (e.g. [{"role": "user", "content": "Hello"}])
        encoding: Tiktoken encoding name

    Returns:
        JSON with total token count, per-message breakdown, and budget
    """
    msgs = json.loads(messages)
    total = count_messages_tokens(msgs, encoding)

    # Per-message breakdown
    breakdown = []
    for msg in msgs:
        msg_tokens = count_messages_tokens([msg], encoding)
        breakdown.append(
            {
                "role": msg.get("role", "unknown"),
                "tokens": msg_tokens,
                "content_preview": str(msg.get("content", ""))[:80],
            }
        )

    _token_budget.consume(total)

    return json.dumps(
        {
            "total_tokens": total,
            "message_count": len(msgs),
            "breakdown": breakdown,
            "encoding": encoding,
            "budget": _token_budget.to_dict(),
        }
    )


@mcp.tool()
@track_telemetry("optimize_messages")
def optimize_messages(
    messages: str,
    max_tokens: int = 8000,
    strategy: str = "smart",
    preserve_recent: int = 6,
    encoding: str = DEFAULT_ENCODING,
) -> str:
    """
    Trim a message history array to fit within a token budget.

    Strategies:
      - tail: Keep the most recent messages
      - head: Keep the oldest messages
      - smart (default): Protect system messages + recent context,
                          compress the middle intelligently

    The 'smart' strategy NEVER removes system/developer messages.

    Args:
        messages: JSON string of the messages array
        max_tokens: Maximum token budget for the output
        strategy: One of 'tail', 'head', 'smart'
        preserve_recent: (smart only) How many recent messages to protect
        encoding: Tiktoken encoding name

    Returns:
        JSON with optimized messages array and diagnostics
    """
    msgs = json.loads(messages)
    result = trim_messages(msgs, max_tokens, strategy, preserve_recent, encoding)
    return json.dumps(result.to_dict())


@mcp.tool()
@track_telemetry("index_knowledge")
def index_knowledge(
    path: str,
    recursive: bool = True,
    force: bool = False,
) -> str:
    """
    Index a file or directory into the local RAG knowledge base.

    Reads text files, splits them into semantic chunks, generates
    multilingual embeddings locally, and stores them in LanceDB.
    Supports: .md, .txt, .py, .js, .ts, .go, .rs, .java, .yaml, .json, etc.

    Files that haven't changed (same SHA-256 hash) are automatically
    skipped to save CPU and disk. Use force=True to re-index anyway.

    Args:
        path: Absolute path to a file or directory to index
        recursive: If path is a directory, whether to recurse into subdirectories
        force: If True, re-index even if file content hasn't changed

    Returns:
        JSON with indexing statistics (files indexed, chunks created, etc.)
    """
    import os

    engine = _get_rag_engine()

    if os.path.isfile(path):
        result = engine.index_file(path, force=force)
    elif os.path.isdir(path):
        result = engine.index_directory(path, recursive=recursive, force=force)
    else:
        result = {"status": "error", "error": f"Path not found: {path}"}

    return json.dumps(result)


@mcp.tool()
@track_telemetry("search_context")
def search_context(
    query: str,
    top_k: int = 5,
    max_tokens: int = 0,
    min_score: float = 0.0,
    max_chunks_per_source: int = 0,
) -> str:
    """
    Search the indexed knowledge base using semantic similarity.

    Finds the most relevant chunks from previously indexed files
    using multilingual embeddings and cosine similarity.

    Args:
        query: The search query (natural language)
        top_k: Number of results to return (default: 5)
        max_tokens: Max token budget for results (0 = no limit).
                    Prevents RAG from flooding the context window.
        min_score: Max cosine distance to accept (0.0 = accept all).
                   Lower distance = more similar. Try 0.5 for strict.
        max_chunks_per_source: Limit chunks per source file (0 = no limit).
                               Try 2 to avoid one file dominating context.

    Returns:
        JSON array of matching chunks with source, score, and text
    """
    engine = _get_rag_engine()
    results = engine.search(
        query,
        top_k=top_k,
        max_tokens=max_tokens,
        min_score=min_score,
        max_chunks_per_source=max_chunks_per_source,
    )

    return json.dumps(
        {
            "query": query,
            "results_count": len(results),
            "results": [r.to_dict() for r in results],
        }
    )


@mcp.tool()
@track_telemetry("cache_context")
def cache_context(
    messages: str,
    rag_query: Optional[str] = None,
    rag_top_k: int = 3,
) -> str:
    """
    Process messages for cache-aware optimization.

    Separates static prefix (system prompts, RAG context) from
    dynamic conversation. Detects when the prefix hasn't changed
    between turns to enable provider-level prompt caching
    (Anthropic/Google/OpenAI cache up to 90% on stable prefixes).

    Optionally injects RAG results into the static prefix.

    Args:
        messages: JSON string of the messages array
        rag_query: Optional RAG search query to inject context
        rag_top_k: Number of RAG results to inject (default: 3)

    Returns:
        JSON with cache-optimized messages and cache metadata
    """
    msgs = json.loads(messages)

    # Optionally fetch RAG context
    rag_context = None
    if rag_query:
        engine = _get_rag_engine()
        results = engine.search(rag_query, top_k=rag_top_k)
        if results:
            rag_context = "\n\n---\n\n".join(f"[{r.source} | chunk {r.chunk_index}]\n{r.text}" for r in results)

    result = _cache_loop.process_messages(msgs, rag_context=rag_context)
    return json.dumps(result)


@mcp.tool()
def rag_stats() -> str:
    """
    Get statistics about the indexed RAG knowledge base.

    Returns:
        JSON with total chunks, database path, and table info
    """
    engine = _get_rag_engine()
    return json.dumps(engine.stats())


@mcp.tool()
def clear_knowledge() -> str:
    """
    Clear all indexed knowledge from the RAG database.

    Returns:
        JSON confirmation of the clear operation
    """
    engine = _get_rag_engine()
    return json.dumps(engine.clear())


@mcp.tool()
def reset_token_budget(
    max_tokens: int = 128_000,
    safety_buffer: float = 0.05,
) -> str:
    """
    Reset the token budget tracker with new limits.

    Args:
        max_tokens: Maximum token limit for the context window
        safety_buffer: Safety buffer percentage (0.05 = 5%)

    Returns:
        JSON with the new budget configuration
    """
    global _token_budget
    _token_budget = TokenBudget(max_tokens=max_tokens, safety_buffer=safety_buffer)
    return json.dumps(_token_budget.to_dict())


@mcp.tool()
@track_telemetry("analyze_context_health")
def analyze_context_health_tool(
    messages: str,
    max_tokens: int = 128_000,
    encoding: str = DEFAULT_ENCODING,
) -> str:
    """
    RFC-002 P4: Analyze the health of a context window.

    Provides a Health Score (0-100) with detailed metrics on:
      - Token utilization (% of budget used)
      - Message redundancy (duplicate detection)
      - System-to-user ratio (prompt domination)
      - Noise (trivial/empty messages)

    Returns actionable recommendations and orchestrator hints
    for proactive context management.

    Args:
        messages: JSON string of the messages array
        max_tokens: Maximum token budget for the context window
        encoding: Tiktoken encoding name

    Returns:
        JSON with health_score, metrics, recommendations, and orchestrator_hints
    """
    msgs = json.loads(messages)
    report = analyze_context_health(msgs, max_tokens, encoding)

    # RFC-002 P3: Include orchestrator info if detected
    orchestrator = get_orchestrator_info()
    result = report.to_dict()
    result["orchestrator"] = orchestrator.to_dict()

    return json.dumps(result)


@mcp.tool()
@track_telemetry("get_orchestration_advice")
def get_orchestration_advice(
    messages: str,
    max_tokens: int = 128_000,
    encoding: str = DEFAULT_ENCODING,
) -> str:
    """
    Return orchestration advice for Gentle AI / MCP orchestrators.

    Combines context health + orchestrator detection into a practical
    next-step contract that upstream orchestrators can consume.

    Args:
        messages: JSON string of the messages array
        max_tokens: Maximum token budget for the context window
        encoding: Tiktoken encoding name

    Returns:
        JSON with detected orchestrator, health, and actionable next steps
    """
    msgs = json.loads(messages)
    report = analyze_context_health(msgs, max_tokens, encoding)
    orchestrator = get_orchestrator_info()

    metrics = report.metrics
    hints = report.orchestrator_hints
    total_tokens = metrics.get("total_tokens", 0)
    usage_percent = metrics.get("token_usage_percent", 0.0)
    redundancy = metrics.get("redundancy_ratio", 0.0)
    estimated_savings = max(0, int(total_tokens * max(redundancy, usage_percent / 100 * 0.2)))

    if hints.get("should_trim_now"):
        recommended_next_tool = "optimize_messages"
        urgency = "high" if usage_percent >= 90 else "medium"
        reason = "Context pressure is high enough that trimming should happen before the next expensive turn."
    elif orchestrator.advisor_mode:
        recommended_next_tool = "cache_context"
        urgency = "low"
        reason = "An orchestrator is present; stabilizing the prefix improves reuse across turns."
    else:
        recommended_next_tool = "analyze_context_health_tool"
        urgency = "low"
        reason = "No orchestrator-specific action is required yet; continue monitoring context health."

    result = {
        "orchestrator": orchestrator.to_dict(),
        "health": report.to_dict(),
        "advice": {
            "recommended_next_tool": recommended_next_tool,
            "urgency": urgency,
            "reason": reason,
            "suggested_strategy": hints.get("suggested_strategy", "smart"),
            "should_trim_now": hints.get("should_trim_now", False),
            "estimated_savings_tokens": estimated_savings,
            "safe_to_index": usage_percent < 85,
            "should_snapshot_context": usage_percent >= 75 or redundancy >= 0.2,
        },
    }
    return json.dumps(result)


# ============================================================
# RESOURCES
# ============================================================


@mcp.resource("status://token_budget")
def token_budget_resource() -> str:
    """Current token budget status: consumed, remaining, usage percentage."""
    result = _token_budget.to_dict()
    result["token_count_cache"] = get_cache_info()
    return json.dumps(result)


@mcp.resource("cache://status")
def cache_status_resource() -> str:
    """Cache performance: hit rate, total lookups, tokens saved estimate."""
    return json.dumps(_cache_loop.get_stats())


@mcp.resource("rag://stats")
def rag_stats_resource() -> str:
    """RAG knowledge base statistics: total chunks, database info."""
    engine = _get_rag_engine()
    return json.dumps(engine.stats())


@mcp.resource("status://orchestrator")
def orchestrator_resource() -> str:
    """RFC-002 P3: Detected orchestrator information and advisor mode status."""
    return json.dumps(get_orchestrator_info().to_dict())


@mcp.resource("status://orchestration")
def orchestration_resource() -> str:
    """Static orchestration contract for upstream AI orchestrators."""
    orchestrator = get_orchestrator_info()
    return json.dumps(
        {
            "detected_orchestrator": orchestrator.to_dict(),
            "integration_level": "heuristic-advisor",
            "capabilities": {
                "count_tokens": "count_tokens_tool",
                "count_messages": "count_messages_tokens_tool",
                "trim": "optimize_messages",
                "cache": "cache_context",
                "health": "analyze_context_health_tool",
                "orchestration_advice": "get_orchestration_advice",
                "rag_search": "search_context",
                "rag_index": "index_knowledge",
            },
            "recommended_flow": [
                "count_messages_tokens_tool",
                "analyze_context_health_tool",
                "get_orchestration_advice",
                "optimize_messages",
                "cache_context",
            ],
            "notes": [
                "Current integration is advisor-based: detection + hints, not a bidirectional handshake.",
                (
                    "Use get_orchestration_advice before expensive turns to decide "
                    "whether to trim, cache, or snapshot context."
                ),
            ],
        }
    )
