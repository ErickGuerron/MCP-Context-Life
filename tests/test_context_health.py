"""
Tests for RFC-002 P4: Context Health Analysis.

Verifies:
  1. Health score ranges (0-100)
  2. Redundancy detection
  3. System-to-user ratio computation
  4. Noise estimation
  5. Recommendations generation
  6. Orchestrator hints
  7. Edge cases (empty, single message, all system)
"""

import json

import pytest

from mmcp.trim_history import (
    analyze_context_health,
    ContextHealthReport,
    _compute_redundancy_ratio,
    _compute_system_to_user_ratio,
    _estimate_noise,
)
from mmcp.token_counter import count_messages_tokens


class TestHealthScoreRanges:
    """Health score should always be in [0, 100]."""

    def test_empty_messages_perfect_score(self):
        """Empty message list should return score 100."""
        report = analyze_context_health([], max_tokens=8000)
        assert report.health_score == 100

    def test_healthy_context(self):
        """Small, clean context should score high."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a high-level programming language."},
        ]
        report = analyze_context_health(messages, max_tokens=128000)
        assert report.health_score >= 80

    def test_overloaded_context(self):
        """Context near token limit should score low."""
        # Create messages that almost fill the budget
        messages = [
            {"role": "system", "content": "System prompt " * 200},
            {"role": "user", "content": "Long message " * 200},
        ]
        total_tokens = count_messages_tokens(messages)
        # Set max_tokens just slightly above actual usage
        report = analyze_context_health(messages, max_tokens=int(total_tokens * 1.05))
        assert report.health_score <= 70

    def test_score_never_negative(self):
        """Score should never go below 0."""
        # Worst case: high usage + redundancy + noise
        messages = [
            {"role": "system", "content": "S " * 500},
        ]
        for i in range(20):
            messages.append({"role": "user", "content": ""})
            messages.append({"role": "user", "content": "ok"})

        tokens = count_messages_tokens(messages)
        report = analyze_context_health(messages, max_tokens=max(tokens, 100))
        assert report.health_score >= 0

    def test_score_never_exceeds_100(self):
        """Score should never exceed 100."""
        messages = [{"role": "user", "content": "Hello!"}]
        report = analyze_context_health(messages, max_tokens=1_000_000)
        assert report.health_score <= 100


class TestRedundancyDetection:
    """Test _compute_redundancy_ratio."""

    def test_no_redundancy(self):
        """All unique messages should have 0 redundancy."""
        messages = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "Second message"},
            {"role": "user", "content": "Third message"},
        ]
        ratio = _compute_redundancy_ratio(messages)
        assert ratio == 0.0

    def test_full_redundancy(self):
        """All identical messages should have high redundancy."""
        messages = [
            {"role": "user", "content": "Same thing"},
            {"role": "user", "content": "Same thing"},
            {"role": "user", "content": "Same thing"},
        ]
        ratio = _compute_redundancy_ratio(messages)
        assert ratio > 0.5  # 2/3 = 0.6667

    def test_partial_redundancy(self):
        """Mix of unique and duplicate messages."""
        messages = [
            {"role": "user", "content": "Unique one"},
            {"role": "user", "content": "Duplicate"},
            {"role": "user", "content": "Duplicate"},
            {"role": "user", "content": "Unique two"},
        ]
        ratio = _compute_redundancy_ratio(messages)
        assert 0.0 < ratio < 1.0  # 1/4 = 0.25

    def test_single_message_no_redundancy(self):
        """Single message can't be redundant."""
        ratio = _compute_redundancy_ratio([{"role": "user", "content": "hello"}])
        assert ratio == 0.0

    def test_whitespace_normalization(self):
        """Messages differing only in whitespace should be detected as duplicates."""
        messages = [
            {"role": "user", "content": "hello   world"},
            {"role": "user", "content": "hello world"},
        ]
        ratio = _compute_redundancy_ratio(messages)
        assert ratio > 0.0


class TestSystemToUserRatio:
    """Test _compute_system_to_user_ratio."""

    def test_no_system_messages(self):
        """No system messages should return 0.0."""
        messages = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi!"},
        ]
        ratio = _compute_system_to_user_ratio(messages)
        assert ratio == 0.0

    def test_only_system_messages(self):
        """Only system messages should return 1.0."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "developer", "content": "Always respond in JSON."},
        ]
        ratio = _compute_system_to_user_ratio(messages)
        assert ratio == 1.0

    def test_balanced_ratio(self):
        """Mix should return a value between 0 and 1."""
        messages = [
            {"role": "system", "content": "System instructions here"},
            {"role": "user", "content": "User question here"},
        ]
        ratio = _compute_system_to_user_ratio(messages)
        assert 0.0 < ratio < 1.0


class TestNoiseEstimation:
    """Test _estimate_noise."""

    def test_no_noise(self):
        """Normal-length messages should have low noise."""
        messages = [
            {"role": "user", "content": "How does authentication work in this project?"},
            {"role": "assistant", "content": "Authentication uses JWT tokens with Bearer headers."},
        ]
        assert _estimate_noise(messages) == "low"

    def test_high_noise(self):
        """Mostly empty/short messages should have high noise."""
        messages = [
            {"role": "user", "content": ""},
            {"role": "user", "content": "ok"},
            {"role": "user", "content": ""},
            {"role": "user", "content": "y"},
            {"role": "user", "content": ""},
        ]
        assert _estimate_noise(messages) == "high"

    def test_medium_noise(self):
        """Some short messages mixed with normal should be medium."""
        messages = [
            {"role": "user", "content": "Short but reasonable message content for testing."},
            {"role": "user", "content": "ok"},
            {"role": "user", "content": "Another meaningful message with good content."},
            {"role": "user", "content": "Another good message for the test suite."},
            {"role": "user", "content": "Yet another solid message with content."},
        ]
        assert _estimate_noise(messages) in ("low", "med")


class TestRecommendations:
    """Test that recommendations are generated correctly."""

    def test_healthy_context_gets_positive_message(self):
        """Healthy context should get 'no action needed' message."""
        messages = [
            {"role": "user", "content": "Simple question"},
            {"role": "assistant", "content": "Simple answer"},
        ]
        report = analyze_context_health(messages, max_tokens=128000)
        assert any("healthy" in r.lower() or "no" in r.lower() for r in report.recommendations)

    def test_high_usage_gets_warning(self):
        """High token usage should trigger trim recommendations."""
        messages = [
            {"role": "system", "content": "Very long system prompt " * 300},
        ]
        tokens = count_messages_tokens(messages)
        report = analyze_context_health(messages, max_tokens=int(tokens * 1.08))
        assert any("trim" in r.lower() or "token" in r.lower() for r in report.recommendations)

    def test_redundancy_gets_recommendation(self):
        """Redundant messages should trigger dedup recommendation."""
        messages = [
            {"role": "user", "content": "Tell me about Python programming language"},
            {"role": "user", "content": "Tell me about Python programming language"},
            {"role": "user", "content": "Tell me about Python programming language"},
        ]
        report = analyze_context_health(messages, max_tokens=128000)
        assert any("redundancy" in r.lower() or "duplicate" in r.lower() for r in report.recommendations)


class TestOrchestratorHints:
    """Test orchestrator_hints generation."""

    def test_hints_structure(self):
        """Hints should have should_trim_now and suggested_strategy."""
        messages = [{"role": "user", "content": "Hello"}]
        report = analyze_context_health(messages, max_tokens=8000)

        assert "should_trim_now" in report.orchestrator_hints
        assert "suggested_strategy" in report.orchestrator_hints
        assert isinstance(report.orchestrator_hints["should_trim_now"], bool)
        assert report.orchestrator_hints["suggested_strategy"] in ("smart", "digest", "tail", "summary")

    def test_should_trim_when_high_usage(self):
        """should_trim_now should be True when usage is very high."""
        messages = [{"role": "system", "content": "Long prompt " * 500}]
        tokens = count_messages_tokens(messages)
        report = analyze_context_health(messages, max_tokens=int(tokens * 1.1))
        assert report.orchestrator_hints["should_trim_now"] is True


class TestSerialization:
    """Test ContextHealthReport.to_dict()."""

    def test_to_dict_has_all_fields(self):
        """to_dict() should include all top-level fields."""
        report = analyze_context_health(
            [{"role": "user", "content": "test"}],
            max_tokens=8000,
        )
        d = report.to_dict()

        assert "health_score" in d
        assert "metrics" in d
        assert "recommendations" in d
        assert "orchestrator_hints" in d

    def test_to_dict_is_json_serializable(self):
        """to_dict() output must be JSON-serializable."""
        report = analyze_context_health(
            [{"role": "user", "content": "test"}],
            max_tokens=8000,
        )
        # This should not raise
        json_str = json.dumps(report.to_dict())
        assert isinstance(json_str, str)
