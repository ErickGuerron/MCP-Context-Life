"""
Tests for AutoInvokeMetrics: async Counter, Histogram, Gauge with Queue emission.
"""

import queue
import time
import threading

import pytest

from mmcp.domain.auto_invoke_metrics import (
    AutoInvokeMetrics,
    Counter,
    Histogram,
    Gauge,
)


class TestCounter:
    """Test Counter metric type."""

    def test_increment_adds_delta(self):
        """Counter.increment() adds delta to current value."""
        c = Counter()
        c.increment("host", "agent", "provider", "model", delta=1)
        assert c.get("host", "agent", "provider", "model") == 1

    def test_increment_multiple_times(self):
        """Multiple increments accumulate correctly."""
        c = Counter()
        c.increment("host", "agent", "provider", "model", delta=1)
        c.increment("host", "agent", "provider", "model", delta=2)
        c.increment("host", "agent", "provider", "model", delta=3)
        assert c.get("host", "agent", "provider", "model") == 6

    def test_multiple_keys_independent(self):
        """Different key combinations maintain separate counts."""
        c = Counter()
        c.increment("host1", "agent1", "provider1", "model1", delta=1)
        c.increment("host2", "agent2", "provider2", "model2", delta=2)
        assert c.get("host1", "agent1", "provider1", "model1") == 1
        assert c.get("host2", "agent2", "provider2", "model2") == 2

    def test_get_returns_zero_for_unknown_key(self):
        """Unknown key returns 0."""
        c = Counter()
        assert c.get("unknown", "unknown", "unknown", "unknown") == 0

    def test_total_returns_sum(self):
        """Counter.total() returns sum of all counts."""
        c = Counter()
        c.increment("host1", "agent1", "provider1", "model1", delta=1)
        c.increment("host2", "agent2", "provider2", "model2", delta=2)
        assert c.total() == 3

    def test_breakdown_returns_dict(self):
        """Counter.breakdown() returns formatted string keys."""
        c = Counter()
        c.increment("opencode", "agent1", "anthropic", "model-a", delta=1)
        bd = c.breakdown()
        assert "opencode/agent1/anthropic/model-a" in bd
        assert bd["opencode/agent1/anthropic/model-a"] == 1


class TestHistogram:
    """Test Histogram metric type."""

    def test_record_adds_observation(self):
        """Histogram.record() adds an observation to the bucket."""
        h = Histogram()
        h.record("host", "agent", "provider", "model", 50.0)
        assert h.get("host", "agent", "provider", "model") == [50.0]

    def test_record_multiple_observations(self):
        """Multiple observations are accumulated."""
        h = Histogram()
        h.record("host", "agent", "provider", "model", 10.0)
        h.record("host", "agent", "provider", "model", 20.0)
        h.record("host", "agent", "provider", "model", 30.0)
        assert h.get("host", "agent", "provider", "model") == [10.0, 20.0, 30.0]

    def test_multiple_keys_independent(self):
        """Different key combinations maintain separate buckets."""
        h = Histogram()
        h.record("host1", "agent1", "provider1", "model1", 100.0)
        h.record("host2", "agent2", "provider2", "model2", 200.0)
        assert h.get("host1", "agent1", "provider1", "model1") == [100.0]
        assert h.get("host2", "agent2", "provider2", "model2") == [200.0]


class TestGauge:
    """Test Gauge metric type."""

    def test_set_overwrites_value(self):
        """Gauge.set() overwrites the previous value."""
        g = Gauge()
        g.set("host", "agent", "provider", "model", 42.0)
        assert g.get("host", "agent", "provider", "model") == 42.0
        g.set("host", "agent", "provider", "model", 100.0)
        assert g.get("host", "agent", "provider", "model") == 100.0

    def test_multiple_keys_independent(self):
        """Different key combinations maintain separate gauges."""
        g = Gauge()
        g.set("host1", "agent1", "provider1", "model1", 1.0)
        g.set("host2", "agent2", "provider2", "model2", 2.0)
        assert g.get("host1", "agent1", "provider1", "model1") == 1.0
        assert g.get("host2", "agent2", "provider2", "model2") == 2.0


class TestAutoInvokeMetrics:
    """Test AutoInvokeMetrics facade."""

    @pytest.fixture(autouse=True)
    def enable_usage_tracking(self):
        """Enable usage_tracking for all tests in this class."""
        import mmcp.infrastructure.environment.config as config_module
        from mmcp.infrastructure.environment.config import reset_config

        original_get_config = config_module.get_config

        class EnabledConfig:
            usage_tracking_enabled = True
            def resolve_cache_db_path(self):
                import tempfile
                from pathlib import Path
                return Path(tempfile.gettempdir()) / "test_context_life.db"

        config_module.get_config = lambda: EnabledConfig()

        yield

        config_module.get_config = original_get_config
        reset_config()

    def test_increment_invokes_increments_counter(self):
        """increment_invokes() increments the invoke counter for the given dimension."""
        metrics = AutoInvokeMetrics()
        metrics.increment_invokes("opencode", "claude-code", "anthropic", "claude-3-5-sonnet")
        metrics.increment_invokes("opencode", "claude-code", "anthropic", "claude-3-5-sonnet")
        metrics.increment_invokes("cursor-ai", "cursor-agent", "openai", "gpt-4o")

        assert metrics._invokes.get("opencode", "claude-code", "anthropic", "claude-3-5-sonnet") == 2
        assert metrics._invokes.get("cursor-ai", "cursor-agent", "openai", "gpt-4o") == 1

    def test_record_tokens_saved_accumulates(self):
        """record_tokens_saved() accumulates saved tokens count via total()."""
        metrics = AutoInvokeMetrics()
        metrics.record_tokens_saved(100)
        metrics.record_tokens_saved(200)
        metrics.record_tokens_saved(50)

        assert metrics._tokens_saved.total() == 350

    def test_record_latency_adds_to_histogram(self):
        """record_latency() adds latency observation to histogram via __total__ sentinel."""
        metrics = AutoInvokeMetrics()
        metrics.record_latency(25.5)
        metrics.record_latency(30.1)
        metrics.record_latency(18.7)

        latencies = metrics._latencies.get("__total__", "__total__", "__total__", "__total__")
        assert len(latencies) == 3
        assert 25.5 in latencies
        assert 30.1 in latencies
        assert 18.7 in latencies

    def test_get_summary_returns_dict(self):
        """get_summary() returns a structured dict with breakdowns."""
        metrics = AutoInvokeMetrics()
        metrics.increment_invokes("opencode", "agent1", "anthropic", "claude-3-5-sonnet")
        metrics.increment_invokes("opencode", "agent1", "anthropic", "claude-3-5-sonnet")
        metrics.increment_invokes("cursor-ai", "agent2", "openai", "gpt-4o")
        metrics.record_tokens_saved(500)
        metrics.record_latency(20.0)

        summary = metrics.get_summary()

        assert "total_invokes" in summary
        assert "total_tokens_saved" in summary
        assert "hosts" in summary
        assert "agents" in summary
        assert "providers" in summary
        assert "models" in summary
        assert summary["total_invokes"] == 3
        assert summary["total_tokens_saved"] == 500

    def test_get_summary_per_host_breakdown(self):
        """get_summary() includes per-host invoke counts."""
        metrics = AutoInvokeMetrics()
        metrics.increment_invokes("opencode", "agent1", "anthropic", "model-a")
        metrics.increment_invokes("opencode", "agent1", "anthropic", "model-a")
        metrics.increment_invokes("cursor-ai", "agent2", "openai", "model-b")

        summary = metrics.get_summary()

        assert "opencode" in summary["hosts"]
        assert "cursor-ai" in summary["hosts"]
        assert summary["hosts"]["opencode"] == 2
        assert summary["hosts"]["cursor-ai"] == 1

    def test_auto_invoke_metrics_has_queue(self):
        """AutoInvokeMetrics has a queue.Queue for async emission."""
        metrics = AutoInvokeMetrics()
        assert hasattr(metrics, "_queue")
        assert isinstance(metrics._queue, queue.Queue)
        metrics.shutdown()


class TestAutoInvokeMetricsBypass:
    """Test usage_tracking.enabled: false bypass."""

    def test_bypass_when_disabled(self):
        """When usage_tracking.enabled is False, metrics recording is skipped."""
        from mmcp.infrastructure.environment.config import reset_config
        from mmcp.domain.auto_invoke_metrics import AutoInvokeMetrics

        reset_config()

        # Create a fresh config with usage_tracking disabled
        from mmcp.infrastructure.environment.config import CLConfig
        config = CLConfig()
        config.usage_tracking_enabled = False

        # Temporarily patch get_config to return disabled config
        import mmcp.infrastructure.environment.config as config_module
        original_get_config = config_module.get_config

        class FakeConfig:
            usage_tracking_enabled = False

        config_module.get_config = lambda: FakeConfig()

        try:
            metrics = AutoInvokeMetrics()
            # increment_invokes should not raise even when tracking is disabled
            metrics.increment_invokes("opencode", "agent", "anthropic", "claude-3-5-sonnet")
            # If bypass works correctly, no event should be emitted to queue
            # (queue may still have events from initialization but not from increment)
            metrics.shutdown()
        finally:
            config_module.get_config = original_get_config
            reset_config()