"""
Trim History Module — Context-Life (CL)

Implements 3 strategies for intelligent message array trimming:
  - tail:  Keep the N most recent messages
  - head:  Keep the N oldest messages
  - smart: Protect system messages + recent context, compress the middle

The smart strategy is the crown jewel — it NEVER touches system messages
and intelligently decides what to drop vs. summarize.

RFC-002 P4: analyze_context_health() — Diagnostic tool that provides a
"Health Score" (0-100) for the current context window with actionable
recommendations and orchestrator hints.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from mmcp.token_counter import count_messages_tokens, count_tokens, DEFAULT_ENCODING


class TrimStrategy(str, Enum):
    TAIL = "tail"
    HEAD = "head"
    SMART = "smart"


@dataclass
class TrimResult:
    """Result of a trim operation with diagnostics."""

    messages: list[dict]
    original_token_count: int
    trimmed_token_count: int
    messages_removed: int
    strategy_used: str

    @property
    def tokens_saved(self) -> int:
        return self.original_token_count - self.trimmed_token_count

    @property
    def reduction_percent(self) -> float:
        if self.original_token_count == 0:
            return 0.0
        return round((self.tokens_saved / self.original_token_count) * 100, 2)

    def to_dict(self) -> dict:
        return {
            "messages": self.messages,
            "diagnostics": {
                "original_tokens": self.original_token_count,
                "trimmed_tokens": self.trimmed_token_count,
                "tokens_saved": self.tokens_saved,
                "reduction_percent": self.reduction_percent,
                "messages_removed": self.messages_removed,
                "strategy": self.strategy_used,
            },
        }


def _is_system_message(message: dict) -> bool:
    """Check if a message has a system-like role."""
    role = message.get("role", "").lower()
    return role in ("system", "developer")


def trim_tail(
    messages: list[dict],
    max_tokens: int,
    encoding: str = DEFAULT_ENCODING,
) -> TrimResult:
    """
    Keep the most recent messages that fit within max_tokens.
    System messages are ALWAYS preserved at the top regardless.
    """
    original_count = count_messages_tokens(messages, encoding)

    if original_count <= max_tokens:
        return TrimResult(
            messages=messages,
            original_token_count=original_count,
            trimmed_token_count=original_count,
            messages_removed=0,
            strategy_used=TrimStrategy.TAIL.value,
        )

    # Separate system messages (always kept) from the rest
    system_msgs = [m for m in messages if _is_system_message(m)]
    non_system_msgs = [m for m in messages if not _is_system_message(m)]

    system_tokens = count_messages_tokens(system_msgs, encoding) if system_msgs else 0
    available_tokens = max_tokens - system_tokens

    # Walk backwards through non-system messages, accumulating
    kept: list[dict] = []
    running_tokens = 0

    for msg in reversed(non_system_msgs):
        msg_tokens = count_messages_tokens([msg], encoding)
        if running_tokens + msg_tokens <= available_tokens:
            kept.insert(0, msg)
            running_tokens += msg_tokens
        else:
            break

    result_messages = system_msgs + kept
    trimmed_count = count_messages_tokens(result_messages, encoding)

    return TrimResult(
        messages=result_messages,
        original_token_count=original_count,
        trimmed_token_count=trimmed_count,
        messages_removed=len(messages) - len(result_messages),
        strategy_used=TrimStrategy.TAIL.value,
    )


def trim_head(
    messages: list[dict],
    max_tokens: int,
    encoding: str = DEFAULT_ENCODING,
) -> TrimResult:
    """
    Keep the oldest messages that fit within max_tokens.
    System messages are ALWAYS preserved at the top regardless.
    """
    original_count = count_messages_tokens(messages, encoding)

    if original_count <= max_tokens:
        return TrimResult(
            messages=messages,
            original_token_count=original_count,
            trimmed_token_count=original_count,
            messages_removed=0,
            strategy_used=TrimStrategy.HEAD.value,
        )

    system_msgs = [m for m in messages if _is_system_message(m)]
    non_system_msgs = [m for m in messages if not _is_system_message(m)]

    system_tokens = count_messages_tokens(system_msgs, encoding) if system_msgs else 0
    available_tokens = max_tokens - system_tokens

    kept: list[dict] = []
    running_tokens = 0

    for msg in non_system_msgs:
        msg_tokens = count_messages_tokens([msg], encoding)
        if running_tokens + msg_tokens <= available_tokens:
            kept.append(msg)
            running_tokens += msg_tokens
        else:
            break

    result_messages = system_msgs + kept
    trimmed_count = count_messages_tokens(result_messages, encoding)

    return TrimResult(
        messages=result_messages,
        original_token_count=original_count,
        trimmed_token_count=trimmed_count,
        messages_removed=len(messages) - len(result_messages),
        strategy_used=TrimStrategy.HEAD.value,
    )


def trim_smart(
    messages: list[dict],
    max_tokens: int,
    preserve_recent: int = 6,
    encoding: str = DEFAULT_ENCODING,
    summary_prompt: Optional[str] = None,
) -> TrimResult:
    """
    Intelligent trimming strategy — the crown jewel of Context-Life.

    Strict Budget Enforcement Ladder:
      1. ALWAYS protect system/developer messages (immutable anchors)
      2. Try to protect the last `preserve_recent` non-system messages
      3. Drop ALL middle messages first
      4. If still over budget → reduce preserve_recent progressively
      5. If STILL over budget → trim system messages to fit
      6. GUARANTEE: output token count ≤ max_tokens

    Args:
        messages: The full message array
        max_tokens: Token budget ceiling
        preserve_recent: Number of recent non-system messages to protect
        encoding: Tiktoken encoding name
        summary_prompt: Optional — not used yet, reserved for LLM summarization
    """
    original_count = count_messages_tokens(messages, encoding)

    if original_count <= max_tokens:
        return TrimResult(
            messages=messages,
            original_token_count=original_count,
            trimmed_token_count=original_count,
            messages_removed=0,
            strategy_used=TrimStrategy.SMART.value,
        )

    # Phase 1: Classify messages
    system_msgs = [m for m in messages if _is_system_message(m)]
    non_system = [m for m in messages if not _is_system_message(m)]

    system_tokens = count_messages_tokens(system_msgs, encoding) if system_msgs else 0

    # Phase 2: Strict ladder — adjust preserve_recent until it fits
    effective_recent = min(preserve_recent, len(non_system))

    while effective_recent >= 0:
        if effective_recent == 0:
            recent_msgs = []
            middle_msgs = non_system
        elif len(non_system) <= effective_recent:
            recent_msgs = non_system
            middle_msgs = []
        else:
            middle_msgs = non_system[:-effective_recent]
            recent_msgs = non_system[-effective_recent:]

        recent_tokens = count_messages_tokens(recent_msgs, encoding) if recent_msgs else 0
        budget_for_middle = max_tokens - system_tokens - recent_tokens

        if budget_for_middle >= 0:
            break  # This preserve_recent level fits

        # Protected messages alone exceed budget — reduce recent
        effective_recent -= 1

    # Phase 3: Fill middle messages (newest first, skip-and-continue)
    kept_middle: list[dict] = []
    running_middle_tokens = 0
    dropped_contents: list[str] = []

    if budget_for_middle > 0 and middle_msgs:
        for msg in reversed(middle_msgs):
            msg_tokens = count_messages_tokens([msg], encoding)
            if running_middle_tokens + msg_tokens <= budget_for_middle:
                kept_middle.insert(0, msg)
                running_middle_tokens += msg_tokens
            else:
                # Skip this message but continue trying smaller ones
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip():
                    dropped_contents.append(f"[{msg.get('role', 'unknown')}]: {content[:120]}")

    # Phase 4: Summary breadcrumb (only if it fits)
    summary_injection: list[dict] = []
    if dropped_contents:
        summary_text = (
            f"[CL Context Summary] {len(dropped_contents)} earlier messages were "
            f"compressed. Topics: "
            + "; ".join(dropped_contents[:3])
        )

        summary_tokens = count_tokens(summary_text, encoding)
        remaining_budget = budget_for_middle - running_middle_tokens
        if remaining_budget >= summary_tokens:
            summary_injection = [
                {"role": "system", "content": summary_text}
            ]

    # Phase 5: Assemble and ENFORCE strict budget
    result_messages = system_msgs + summary_injection + kept_middle + recent_msgs
    trimmed_count = count_messages_tokens(result_messages, encoding)

    # Strict enforcement pass 1: drop middle and summary
    while trimmed_count > max_tokens and (kept_middle or summary_injection):
        if kept_middle:
            kept_middle.pop(0)
        elif summary_injection:
            summary_injection = []

        result_messages = system_msgs + summary_injection + kept_middle + recent_msgs
        trimmed_count = count_messages_tokens(result_messages, encoding)

    # Strict enforcement pass 2: drop recent messages one by one
    while trimmed_count > max_tokens and recent_msgs:
        recent_msgs.pop(0)
        result_messages = system_msgs + recent_msgs
        trimmed_count = count_messages_tokens(result_messages, encoding)

    # Strict enforcement pass 3: oversized system anchors — compact into digest
    if trimmed_count > max_tokens and system_msgs:
        # Build a compressed policy digest from all system messages
        digest_parts: list[str] = []
        for msg in system_msgs:
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                # Take first N chars of each system message
                digest_parts.append(content[:200])

        digest_text = (
            "[CL System Digest — original system instructions were compressed to fit budget]\n"
            + "\n---\n".join(digest_parts)
        )

        # Iteratively truncate digest until it fits
        while count_tokens(digest_text, encoding) > max_tokens - 10 and len(digest_text) > 100:
            digest_text = digest_text[: len(digest_text) * 3 // 4]

        result_messages = [{"role": "system", "content": digest_text}]
        trimmed_count = count_messages_tokens(result_messages, encoding)

    return TrimResult(
        messages=result_messages,
        original_token_count=original_count,
        trimmed_token_count=trimmed_count,
        messages_removed=len(messages) - len(result_messages),
        strategy_used=TrimStrategy.SMART.value,
    )


def trim_messages(
    messages: list[dict],
    max_tokens: int,
    strategy: str = "smart",
    preserve_recent: int = 6,
    encoding: str = DEFAULT_ENCODING,
) -> TrimResult:
    """
    Main entry point — dispatches to the correct strategy.

    Args:
        messages: OpenAI-style message array
        max_tokens: Maximum token budget
        strategy: One of 'tail', 'head', 'smart'
        preserve_recent: (smart only) How many recent messages to protect
        encoding: Tiktoken encoding to use
    """
    strategy_enum = TrimStrategy(strategy.lower())

    if strategy_enum == TrimStrategy.TAIL:
        return trim_tail(messages, max_tokens, encoding)
    elif strategy_enum == TrimStrategy.HEAD:
        return trim_head(messages, max_tokens, encoding)
    elif strategy_enum == TrimStrategy.SMART:
        return trim_smart(messages, max_tokens, preserve_recent, encoding)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")


# ============================================================
# RFC-002 P4: Context Health Analysis
# ============================================================


@dataclass
class ContextHealthReport:
    """RFC-002 P4: Diagnostic report for context window health."""

    health_score: int  # 0-100
    metrics: dict = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    orchestrator_hints: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "health_score": self.health_score,
            "metrics": self.metrics,
            "recommendations": self.recommendations,
            "orchestrator_hints": self.orchestrator_hints,
        }


def _compute_redundancy_ratio(messages: list[dict]) -> float:
    """
    Detect duplicate/near-duplicate messages by content hash.

    Returns a ratio from 0.0 (no redundancy) to 1.0 (all duplicates).
    """
    if len(messages) <= 1:
        return 0.0

    content_hashes: list[str] = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            # Normalize whitespace for comparison
            normalized = " ".join(content.split()).strip().lower()
            content_hashes.append(normalized)

    if not content_hashes:
        return 0.0

    total = len(content_hashes)
    unique = len(set(content_hashes))
    duplicates = total - unique

    return round(duplicates / total, 4) if total > 0 else 0.0


def _compute_system_to_user_ratio(
    messages: list[dict],
    encoding: str = DEFAULT_ENCODING,
) -> float:
    """
    Compute the ratio of system/developer tokens to total tokens.

    High ratios (> 0.5) indicate the context is dominated by system
    instructions, leaving little room for conversation history.
    """
    system_tokens = 0
    total_tokens = 0

    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            tokens = count_tokens(content, encoding)
        elif isinstance(content, (dict, list)):
            tokens = count_tokens(json.dumps(content), encoding)
        else:
            tokens = 0

        total_tokens += tokens
        if _is_system_message(msg):
            system_tokens += tokens

    if total_tokens == 0:
        return 0.0

    return round(system_tokens / total_tokens, 4)


def _estimate_noise(messages: list[dict]) -> str:
    """
    Estimate noise level based on message quality heuristics.

    Noise indicators:
      - Very short messages (< 5 chars)
      - Empty content messages
      - High ratio of single-word exchanges
    """
    if not messages:
        return "low"

    non_system = [m for m in messages if not _is_system_message(m)]
    if not non_system:
        return "low"

    short_count = 0
    empty_count = 0

    for msg in non_system:
        content = msg.get("content", "")
        if isinstance(content, str):
            stripped = content.strip()
            if not stripped:
                empty_count += 1
            elif len(stripped) < 5:
                short_count += 1

    noise_ratio = (short_count + empty_count) / len(non_system)

    if noise_ratio > 0.3:
        return "high"
    elif noise_ratio > 0.1:
        return "med"
    return "low"


def analyze_context_health(
    messages: list[dict],
    max_tokens: int,
    encoding: str = DEFAULT_ENCODING,
) -> ContextHealthReport:
    """
    RFC-002 P4: Analyze the health of a context window.

    Computes a health score (0-100) based on:
      - Token utilization (are we close to the limit?)
      - Redundancy (duplicate messages eating tokens)
      - System-to-user ratio (is the system prompt dominating?)
      - Noise (empty/trivial messages wasting space)

    Returns actionable recommendations and orchestrator hints
    for proactive context management.

    Args:
        messages: OpenAI-style message array
        max_tokens: Maximum token budget for the context
        encoding: Tiktoken encoding name

    Returns:
        ContextHealthReport with score, metrics, and recommendations
    """
    if not messages:
        return ContextHealthReport(
            health_score=100,
            metrics={
                "redundancy_ratio": 0.0,
                "system_to_user_ratio": 0.0,
                "noise_estimate": "low",
                "token_usage_percent": 0.0,
                "total_tokens": 0,
                "message_count": 0,
            },
            recommendations=["Context is empty — no optimization needed."],
            orchestrator_hints={
                "should_trim_now": False,
                "suggested_strategy": "smart",
            },
        )

    # --- Compute metrics ---
    total_tokens = count_messages_tokens(messages, encoding)
    usage_percent = round((total_tokens / max_tokens) * 100, 2) if max_tokens > 0 else 0.0
    redundancy = _compute_redundancy_ratio(messages)
    sys_ratio = _compute_system_to_user_ratio(messages, encoding)
    noise = _estimate_noise(messages)

    # --- Compute health score (0-100) ---
    score = 100

    # Penalty: Token usage approaching limit
    if usage_percent > 90:
        score -= 40
    elif usage_percent > 75:
        score -= 25
    elif usage_percent > 60:
        score -= 10

    # Penalty: Redundancy
    if redundancy > 0.3:
        score -= 25
    elif redundancy > 0.1:
        score -= 10

    # Penalty: System prompt domination
    if sys_ratio > 0.7:
        score -= 20
    elif sys_ratio > 0.5:
        score -= 10

    # Penalty: Noise
    noise_penalty = {"low": 0, "med": 5, "high": 15}
    score -= noise_penalty.get(noise, 0)

    # Clamp to [0, 100]
    score = max(0, min(100, score))

    # --- Generate recommendations ---
    recommendations: list[str] = []

    if usage_percent > 90:
        recommendations.append(
            "⚠️ CRITICAL: Token usage is above 90%. Trim immediately to avoid overflow."
        )
    elif usage_percent > 75:
        recommendations.append(
            "Token usage is high (>75%). Consider trimming older messages."
        )

    if redundancy > 0.1:
        recommendations.append(
            f"Detected {redundancy:.0%} redundancy. Remove duplicate messages to free tokens."
        )

    if sys_ratio > 0.5:
        recommendations.append(
            f"System messages consume {sys_ratio:.0%} of tokens. "
            "Consider condensing system instructions."
        )

    if noise == "high":
        recommendations.append(
            "High noise detected — many very short or empty messages. "
            "These waste token budget with minimal context value."
        )

    if not recommendations:
        recommendations.append("Context is healthy — no immediate action needed.")

    # --- Orchestrator hints ---
    should_trim = usage_percent > 80 or redundancy > 0.2

    if usage_percent > 85:
        suggested = "smart"
    elif redundancy > 0.2:
        suggested = "digest"
    elif noise == "high":
        suggested = "tail"
    else:
        suggested = "smart"

    return ContextHealthReport(
        health_score=score,
        metrics={
            "redundancy_ratio": redundancy,
            "system_to_user_ratio": sys_ratio,
            "noise_estimate": noise,
            "token_usage_percent": usage_percent,
            "total_tokens": total_tokens,
            "max_tokens": max_tokens,
            "message_count": len(messages),
        },
        recommendations=recommendations,
        orchestrator_hints={
            "should_trim_now": should_trim,
            "suggested_strategy": suggested,
        },
    )
